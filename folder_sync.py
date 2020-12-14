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
from threading import Thread

configuration = parse_config.ConfPacket()
configs = configuration.load_config('SYNC_FOLDERS, LOG_FOLDER, SYNC_TIMES, SYNC_EXTENSIONS, ZABBIX')

files_destination_md5=dict()
files_source_md5=dict()
error_counter = 0
metric_value = 0
in_event = 0
in_sync = 0

class Waiter(Thread):
    def run(self):
        while 1:
            time.sleep(int(configs['ZABBIX']['send_metrics_interval']))
            global metric_value
            send_status_metric(metric_value)

def send_status_metric(value):
    try:
        packet = [
            ZabbixMetric(configs['ZABBIX']['hostname'], configs['ZABBIX']['key'], value)
        ]
        ZabbixSender(zabbix_server=configs['ZABBIX']['zabbix_server'], zabbix_port=int(configs['ZABBIX']['port'])).send(packet)
    except Exception as err:
        adiciona_linha_log("Falha de conexão com o Zabbix - "+str(err))

def adiciona_linha_log(texto):
    dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    mes_ano = datetime.now().strftime('_%Y%m')
    print(dataFormatada, texto)
    try:
        log_file = configs['LOG_FOLDER']['log_folder']+'log'+mes_ano+'.txt'
        f = open(log_file, "a")
        f.write(dataFormatada + texto +"\n")
        f.close()
    except Exception as err:
        print(dataFormatada, err)
        
def digest(filepath):
    try:
        path, filename = os.path.split(filepath)
        with open(filepath, 'rb') as file:
            data = file.read() + filename.encode()   
            md5_returned = hashlib.md5(data).hexdigest()
        return md5_returned
    except Exception as err:
        adiciona_linha_log("Falha durante digest - "+str(err))

def filetree(source, dest, sync_name):
    try: 
        sync_ext = configs['SYNC_EXTENSIONS'][sync_name].split(", ")
    except:
        sync_ext = []

    files_destination_md5.clear()
    files_source_md5.clear()
    
    try:
        debug = 'scan dest'
        for e in os.scandir(dest):
            if e.is_file():
                filestring = str(e)
                file_array = filestring.split('\'')
                filename = file_array[1]
                if (not os.path.splitext(filename)[1][1:] in sync_ext) & (len(sync_ext) > 0):
                    continue
                filepath = os.path.join(dest,filename)
                files_destination_md5[filename]=digest(filepath)
              
        debug = 'scan source'
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

        debug = 'remove files'
        for file in files_destination_md5:
            path_dest = os.path.join(dest, file)
            if file not in files_source_md5:
                os.remove(path_dest)
                adiciona_linha_log("Removido: " + str(path_dest))
                files_to_remove.append(file)

        debug = 'destination.pop'  
        for item in files_to_remove:
            files_destination_md5.pop(item)

        debug = 'copy files'
        for file in files_source_md5:
            path_source = os.path.join(source, file)
            path_dest = os.path.join(dest, file)
            if file not in files_destination_md5:
                shutil.copy(path_source, path_dest)                
                files_destination_md5[file]=digest(path_dest)
                adiciona_linha_log("Copiado: " + str(path_source) + " para " + str(path_dest))           
            else:            
                if files_source_md5[file] != files_destination_md5[file]:
                    shutil.copy(path_source, path_dest)
                    adiciona_linha_log("Sobrescrito: " + str(path_source) + " para " + str(path_dest))
        return 0

    except Exception as err:
        send_status_metric(1)  
        adiciona_linha_log(str(err)+debug)
        return 1

def sync_all_folders():
    try:
        global in_event
        while (in_event == 1):
            time.sleep(1)
        global in_sync
        in_sync = 1
        global error_counter
        global metric_value
        error_counter = 0
        for item in configs['SYNC_FOLDERS']:
            paths = (configs['SYNC_FOLDERS'][item]).split(', ')
            error_counter += filetree(paths[0], paths[1], item)
            time.sleep(1)
        if error_counter > 0: 
            metric_value = 1
        else:
            metric_value = 0
        in_sync = 0
    except Exception as err:
        adiciona_linha_log("Falha durante execução da função sync_all_folders - "+str(err))

class Event(LoggingEventHandler):
    try:
        def dispatch(self, event): 
            global in_sync
            while(in_sync == 1):
                time.sleep(1)
            global in_event
            in_event = 1

            LoggingEventHandler()
            adiciona_linha_log(str(event))
            path_event = str(event.src_path)
            for item in configs['SYNC_FOLDERS']:
                paths = (configs['SYNC_FOLDERS'][item]).split(', ')
                if paths[0] in path_event:
                    error = filetree(paths[0], paths[1], item)
            if error > 0: 
                send_status_metric(1)
            else:
                send_status_metric(0)  
            
            in_event = 0
    
    except Exception as err:
        send_status_metric(1)  
        adiciona_linha_log("Logging event handler erro - "+str(err))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
      
    event_handler = Event()
    observer = Observer()
    Waiter().start()

    for item in configs['SYNC_FOLDERS']:
        try:
            host = (configs['SYNC_FOLDERS'][item]).split(', ')
            observer.schedule(event_handler, host[0], recursive=True)
        except Exception as err:
            adiciona_linha_log(str(err)+host[0])

    observer.start()

    try:
        while True:
            sleep_time = int(configs['SYNC_TIMES']['sync_with_no_events_time'])
            if (sleep_time > 0):
                time.sleep(sleep_time)
                sync_all_folders()
            else:
                time.sleep(30)
          
    except KeyboardInterrupt:
        observer.stop()
    observer.join()