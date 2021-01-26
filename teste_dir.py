import os
import time


pathfile = os.path.join("\\\\10.147.10.11\RadioComercial\Programacao","")
print("\n\n\n\n\n\n\nn\n\n\n\n\n")
for item in os.scandir(pathfile):
    print(item.name, end=" ")   

print("\n----------------------------------------\n")
 
for item in os.listdir(pathfile):
    print(item, end=" ")   

    
    