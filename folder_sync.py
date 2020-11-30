import sys
import time
import logging
import shutil
import parse_config
import os
import hashlib
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from datetime import date, datetime
from pyzabbix import ZabbixMetric, ZabbixSender

configuration = parse_config.ConfPacket()
configs = configuration.load_config('SYNC_FOLDERS, LOG_FOLDER, SYNC_TIMES, SYNC_EXTENSIONS, ZABBIX')

files_destination_md5=dict()
files_source_md5=dict()
error_counter = 0
metric_value = 0

def send_status_metric(value):
    packet = [
        ZabbixMetric(configs['ZABBIX']['hostname'], configs['ZABBIX']['key'], value)
    ]
    ZabbixSender(zabbix_server=configs['ZABBIX']['zabbix_server'], zabbix_port=int(configs['ZABBIX']['port'])).send(packet)

def adiciona_linha_log(texto):
    try:
        log_file = configs['LOG_FOLDER']['log_file']
        f = open(log_file, "a")
        dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        f.write(dataFormatada + texto +"\n")
        f.close()
        print(dataFormatada, texto)
    except Exception as err:
        dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(dataFormatada, err)
        
def digest(filepath):
    path, filename = os.path.split(filepath)
    with open(filepath, 'rb') as file:
        data = file.read() + filename.encode()   
        md5_returned = hashlib.md5(data).hexdigest()
    return md5_returned

def filetree(source, dest, sync_name):
    try: 
        sync_ext = configs['SYNC_EXTENSIONS'][sync_name].split(", ")
    except:
        sync_ext = []

    files_destination_md5.clear()
    files_source_md5.clear()
    
    try:
        for e in os.scandir(dest):
            if e.is_file():
                filestring = str(e)
                file_array = filestring.split('\'')
                filename = file_array[1]
                if (not os.path.splitext(filename)[1][1:] in sync_ext) & (len(sync_ext) > 0):
                    continue
                filepath = os.path.join(dest,filename)
                files_destination_md5[filename]=digest(filepath)
              
        for e in os.scandir(source):
            if e.is_file():
                filestring = str(e)
                file_array = filestring.split('\'')
                filename = file_array[1]                
                if (not os.path.splitext(filename)[1][1:] in sync_ext) & (len(sync_ext) > 0):
                    continue
                filepath = os.path.join(source,filename)                
                files_source_md5[filename]=digest(filepath)

        files_to_remove=[]

        for file in files_destination_md5:
            if file not in files_source_md5:
                path = os.path.join(dest, file)
                os.remove(path)
                adiciona_linha_log("Removido: " + str(path))
                files_to_remove.append(file)
            
        for item in files_to_remove:
            files_destination_md5.pop(item)

        for file in files_source_md5:
            if file not in files_destination_md5:
                path_source = os.path.join(source, file)
                path_dest = os.path.join(dest, file)
                shutil.copy(path_source, path_dest)                
                adiciona_linha_log("Copiado: " + str(path_source) + " para " + str(path_dest))           
                filepath = os.path.join(dest,file)
                files_destination_md5[file]=digest(filepath)
            else:            
                if files_source_md5[file] != files_destination_md5[file]:
                    path_source = os.path.join(source, file)
                    path_dest = os.path.join(dest, file)
                    shutil.copy(path_source, path_dest)
                    adiciona_linha_log("Sobrescrito: " + str(path_source) + " para " + str(path_dest))
        return 0

    except Exception as err:
        dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(dataFormatada, err)
        adiciona_linha_log(str(err))
        return 1

def sync_all_folders():
    global error_counter
    error_counter = 0
    for item in configs['SYNC_FOLDERS']:
        paths = (configs['SYNC_FOLDERS'][item]).split(', ')
        error_counter += filetree(paths[0], paths[1], item)
    if error_counter > 0: 
        global metric_value
        metric_value = 1
    else:
         metric_value = 0

class Event(LoggingEventHandler):
    try:
        def dispatch(self, event):
            LoggingEventHandler()
            adiciona_linha_log(str(event))
            path_event = str(event.src_path)
            for item in configs['SYNC_FOLDERS']:
                global error_counter
                paths = (configs['SYNC_FOLDERS'][item]).split(', ')
                if paths[0] in path_event:
                    error_counter += filetree(paths[0], paths[1], item)
                if error_counter > 0: 
                    metric_value = 1
                else:
                    metric_value = 0

    except Exception as err:
        dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(dataFormatada, "Erro: ",err)
        adiciona_linha_log(str(err))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
      
    event_handler = Event()
    observer = Observer()

    for item in configs['SYNC_FOLDERS']:
        try:
            host = (configs['SYNC_FOLDERS'][item]).split(', ')
            observer.schedule(event_handler, host[0], recursive=True)
        except Exception as err:
            print("Erro ao carregar o diretório: ", host[0])
            adiciona_linha_log(str(err)+host[0])

    observer.start()
    try:
        while True:
            sleep_time = int(configs['SYNC_TIMES']['sync_with_no_events_time'])
            send_status_metric(metric_value)
            if (sleep_time > 0):
                time.sleep(sleep_time)
                sync_all_folders()
            else:
                time.sleep(30)
          
    except KeyboardInterrupt:
        observer.stop()
    observer.join()