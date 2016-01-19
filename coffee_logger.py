#!/usr/bin/env python 

import subprocess
import datetime
import Adafruit_CharLCD as LCD
from Queue 		import Queue
import threading, shlex, traceback
from time 		import sleep
import numpy
import os
import pandas as pd

class Command(object):
    """
    Enables to run subprocess commands in a different thread with TIMEOUT option.
    Based on jcollado's solution:
    http://stackoverflow.com/questions/1191374/subprocess-with-timeout/4825933#4825933
    """
    command = None
    process = None
    status = None
    output, error = '', ''

    def __init__(self, command):
        if isinstance(command, basestring):
            command = shlex.split(command)
        self.command = command

    def run(self, timeout=None, **kwargs):
        """ Run a command then return: (status, output, error). """
        def target(**kwargs):
            try:
                self.process = subprocess.Popen(self.command, **kwargs)
                self.output, self.error = self.process.communicate()
                self.status = self.process.returncode
            except:
                self.error = traceback.format_exc()
                self.status = -1
        # default stdout and stderr
        if 'stdout' not in kwargs:
            kwargs['stdout'] = subprocess.PIPE
        if 'stderr' not in kwargs:
            kwargs['stderr'] = subprocess.PIPE
        # thread
        thread = threading.Thread(target=target, kwargs=kwargs)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()
        return self.status, self.output, self.error


#Communication with Adafruit PN532
def rfid():
    res = subprocess.Popen("nfc-poll",stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout, stderr = res.communicate()
    return([stdout, stderr])

#Formatting of the PN532 output
def rfid_ID(input):
    if input[0] == 0: #0 for successfully executed command; -15 for failure 
	uid = str.splitlines(input[1])[5] #unformatted UID at position 5
	uid_formatted = str.replace(str.strip(str.split(uid,':')[1])," ", "") # remove empty spa$
        return uid_formatted
    else:
	return False

def saveUID(ID, money, filename):
    data = pd.read_csv(filename, delimiter='\t')    
    frame = pd.DataFrame([[datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), ID, money]], columns=['Date', 'Time', 'UID', 'Money'])
    data_new = data.append(frame, ignore_index=True)
    data_new.to_csv(filename, sep='\t', index=False)

def acc_balance(ID, filename):
    data = pd.read_csv(filename, delimiter='\t')
    UIDindizes = data.UID[data.UID == ID].index.tolist() # find indizes with match UID
    balance =  sum(data.Money[UIDindizes])
    return balance

def charge(ID, filename, money):
    if ID != False:
	data = pd.read_csv(filename, delimiter='\t')
	frame = pd.DataFrame([[datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), ID, money]], columns=['Date', 'Time', 'UID', 'Money'])
        data_new = data.append(frame, ignore_index=True)
        data_new.to_csv(filename, sep='\t', index=False)
	return True
    else:    
        return False

def diff_balance(ID, filename, money):
    data = pd.read_csv(filename, delimiter='\t')
    if any(data.UID.str.contains(ID)):
        indizes = data.UID[data.UID==ID].index[0]
        data.iloc[indizes] = [datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), ID, data.iloc[indizes,3] + money]
        data.to_csv(filename, sep='\t', index=False)
    else:
        frame = pd.DataFrame([[datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), ID, money]], columns=['Date', 'Time', 'UID', 'Money'])
        data_new = data.append(frame, ignore_index=True)
        data_new.to_csv(filename, sep='\t', index=False)  

def lcdmenu(poll_time, money): #poll_time in s, money in EUR
    lcd.clear()
    lcd.message("Swipe RFID tag\n")
    lcd.message("ID:waiting")
    lcd.set_cursor(3,6)
    UID = rfid_ID(Command("nfc-poll").run(timeout=poll_time))
    if (UID != False):
         lcd.set_cursor(3,6)
         lcd.message(UID)
         sleep(1)
         charge(UID, logfile, money)
         lcd.clear()
         lcd.message("Transaction\ncomplete!")
         sleep(1)
         lcd.clear()
         lcd.message("New Balance:\n" + str(acc_balance(UID, logfile)) + " \x01" )
         sleep(2)
         pass
          
    else:
         lcd.clear()
         lcd.message('No transaction')
         sleep(1.5)
         pass
         
    
#Initialize Coffee logger
coffee_price = -0.25 # Coffee price in EUR
path = '/home/pi/RFID-Coffee' #path to directory    
log = "coffee_log_140116.txt" #logfile
logfile = os.path.join(path, log)
diffsave = "coffee_diff_savelog.txt"

#Initialize LCD

lcd	       = LCD.Adafruit_CharLCDPlate()
LCD_QUEUE      = Queue()
lcd.create_char(1, [3, 4, 30, 8, 30, 9, 7, 0])


# ----------------------------  
# WORKER THREAD  
# ----------------------------  
  
# Define a function to run in the worker thread  
def update_lcd(q):  
     
   while True:  
      msg = q.get()  
      # if we're falling behind, skip some LCD updates  
      while not q.empty():  
         q.task_done()  
         msg = q.get()  
      lcd.set_cursor(0,0)  
      lcd.message(msg)
      sleep(0.2)  
      q.task_done()  
   return 

#Debounce buttons
  
def read_buttons():  
   if (lcd.is_pressed(LCD.UP)    != 0 or\
       lcd.is_pressed(LCD.DOWN)  != 0 or\
       lcd.is_pressed(LCD.LEFT)  != 0 or\
       lcd.is_pressed(LCD.RIGHT) != 0 ):  
      while (lcd.is_pressed(LCD.UP)    != 0 or\
             lcd.is_pressed(LCD.DOWN)  != 0 or\
             lcd.is_pressed(LCD.LEFT)  != 0 or\
             lcd.is_pressed(LCD.RIGHT) != 0 ):
           sleep(0.05) # break
      return buttons

# Main program

MENU_LIST = [
      '1. Pay Coffee \n             ',
      '2. Load Money \n +1.00 \x01  ', #\x0 to interpret created char EUR-symbol as hex
      '3. Load Money \n +2.00 \x01  ',
      '4. Load Money \n +5.00 \x01  ',
      '5. Load Money \n +10.00 \x01  ',
      '6. Load Money \n +20.00 \x01  ',
      '7. Load Money \n +50.00 \x01 ']

def main():  
    # Setup AdaFruit LCD Plate    
   #lcd.begin(16,2)  
   lcd.clear()  

   # Create the worker thread and make it a daemon  
   worker = threading.Thread(target=update_lcd, args=(LCD_QUEUE,))  
   worker.setDaemon(True)  
   worker.start()  

   # Welcome
   LCD_QUEUE.put('Welcome to IAPPs\nCoffee kitty', True)  
   sleep(2)
   lcd.clear()  

#   MENU_LIST = [  
#      '1. Pay Coffee \n             ',  
#      '2. Load Money \n +1.00 \x01  ', #\x0 to interpret created char EUR-symbol as hex   
#      '3. Load Money \n +2.00 \x01  ',  
#      '4. Load Money \n +5.00 \x01  ',  
#      '5. Load Money \n +10.00 \x01  ',  
#      '6. Load Money \n +20.00 \x01  ',  
#      '7. Load Money \n +50.00 \x01 ']  
  
   item = 0  
   lcd.clear()
   LCD_QUEUE.put(MENU_LIST[item], True)  
  
   keep_looping = True  
   #press = read_buttons()
   while (keep_looping):     
      # DOWN button  
      if(lcd.is_pressed(LCD.DOWN) == 1):
         sleep(0.5)  
         item -= 1  
         if(item < 0):  
            item = len(MENU_LIST) - 1  
         LCD_QUEUE.put(MENU_LIST[item], True)  
  
      # UP button  
      elif(lcd.is_pressed(LCD.UP) == 1):  
         sleep(0.5)
	 item += 1  
         if(item >= len(MENU_LIST)):  
            item = 0  
         LCD_QUEUE.put(MENU_LIST[item], True)  
  
      # SELECT button = exit  
      elif(lcd.is_pressed(LCD.SELECT) == 1):  
         keep_looping = False  
  
         # Take action  
         if(item == 0): 
            # 1. Pay Coffee  
            lcdmenu(10, -0.25)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)

         elif(item == 1):  
            # 2. Load 1.00 EUR
            lcdmenu(10, 1.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)
            
         elif(item == 2):  
            # 3. Load 2.00 EUR
            lcdmenu(10, 2.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)  
              
         elif(item == 3):  
            # 4. Load 5.00 EUR 
            lcdmenu(10, 5.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)
  
         elif(item == 4):  
            # 5. Load 10.00 EUR  
            lcdmenu(10, 10.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)
  
         elif(item == 5):  
            # 6. Load 20.00 EUR  
            lcdmenu(10, 20.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)

         elif(item == 6):
            # 7. Load 50.00 EUR
            lcdmenu(10, 50.00)
            keep_looping = True
            LCD_QUEUE.put(MENU_LIST[item], True)

  
      else:
	pass  
         #delay_milliseconds(99)
   
if __name__ == '__main__':
    main() 
