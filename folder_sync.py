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

configuration = parse_config.ConfPacket()
configs = configuration.load_config('SYNC_FOLDERS, LOG_FOLDER, SYNC_TIMES')

files_destination_md5=dict()
files_source_md5=dict()

def adiciona_linha_log(texto):
    try:
        log_file = configs['LOG_FOLDER']['log_file']
        f = open(log_file, "a")
        dataFormatada = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        f.write(dataFormatada + texto +"\n")
        f.close()
        print(texto)
    except Exception as err:
        print(err)        

def filetree(source, dest):
    try:
        files_destination_md5.clear()
        files_source_md5.clear()
        for e in os.scandir(dest):
            if e.is_file():
                filestring = str(e)
                file_array = filestring.split('\'')
                file = file_array[1]
                path_dest = os.path.join(dest,file)
                with open(path_dest) as file_to_check:
                    data = file_to_check.read() + file   
                    md5_returned = hashlib.md5(str(data).encode('utf-8')).hexdigest()
                files_destination_md5[file]=md5_returned
    
        for e in os.scandir(source):
            if e.is_file():
                filestring = str(e)
                file_array = filestring.split('\'')
                file = file_array[1]
                path_source = os.path.join(source,file)
                with open(path_source) as file_to_check:
                    data = file_to_check.read() + file   
                    md5_returned = hashlib.md5(str(data).encode('utf-8')).hexdigest()
                files_source_md5[file]=md5_returned

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
            
                path_dest = os.path.join(dest,file)
                with open(path_dest) as file_to_check:
                    data = file_to_check.read() + path_dest   
                    md5_returned = hashlib.md5(str(data).encode('utf-8')).hexdigest()
                files_destination_md5[file]=md5_returned

            else:            
                if files_source_md5[file] != files_destination_md5[file]:
                    path_source = os.path.join(source, file)
                    path_dest = os.path.join(dest, file)
                    shutil.copy(path_source, path_dest)
                    adiciona_linha_log("Sobrescrito: " + str(path_source) + " para " + str(path_dest))
    except Exception as err:
        print(err)
        adiciona_linha_log(str(err))

def sync_all_folders():
    for item in configs['SYNC_FOLDERS']:
        paths = (configs['SYNC_FOLDERS'][item]).split(', ')
        filetree(paths[0], paths[1])


class Event(LoggingEventHandler):
    try:
        def dispatch(self, event):
            LoggingEventHandler()
            adiciona_linha_log(str(event))
            path_event = str(event.src_path)
            for item in configs['SYNC_FOLDERS']:
                paths = (configs['SYNC_FOLDERS'][item]).split(', ')
                if paths[0] in path_event:
                    filetree(paths[0], paths[1])
    except Exception as err:
        print("Erro: ",err)
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
            sleep_time = configs['SYNC_TIMES']['sync_with_no_events_time']
            if (sleep_time > 0):
                time.sleep(sleep_time)
                print("Synchronizing...")
                sync_all_folders()
            else:
                time.sleep(30)
            print("ENGENHARIA NSC - Sincronizador de Diretórios")
            print("Para verificar os diretórios, consulte o arquivo 'config.ini'.")
          
    except KeyboardInterrupt:
        observer.stop()
    observer.join()