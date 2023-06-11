#System libs:
import time, digitalio,pwmio, random, datetime
import busio, board 
import countio, asyncio

#voor multithreading (het gebruiken van de tweede core op de RPI Pico)
import _thread

#Modules/Screen libs:
import sdcardio, storage
from os import listdir

from adafruit_rgb_display import color565
from adafruit_rgb_display.ili9341 import ILI9341
import roboticsmasters_mpu9250
import adafruit_ds3231, adafruit_gps

#for speed calculation:
import math

#custom lib to generate image for display:
import GUI_Generator

#Buttons:
RecordingButton_pin = board.GP4
CruiseControlButton_pin = board.GP27
CruiseControlOUT_pin = board.GP26_A0

#SD-slot:
SD_Select = board.GP9
SD_DetectPin = board.GP10

#HC-12 UART verbinding
HC_12_TX = board.GP12
HC_12_RX = board.GP13

#NEO-6M (GPS) UART (Markering op PCB van het moederbord is de markering van de pi pico, niet de GPS):
#Dus: RX (GPS) -> TX (PICO GP0)
#TX (GPS) -> RX (PICO GP1)
GPS_UART_RX = board.GP0 
GPS_UART_TX = board.GP1

#LCD Zooi:
LCD_CS = board.GP14
TP_CS = board.GP15
LCD_RS = board.GP11
LCD_RESET = board.GP18


#-----------------------------------------------------------------------------
#Dit gedeelde is voor het optische draaisensor, als je deze ooit gaat gebruiken om de snelheid te meten:
#OPTIC_SENSOR_ANALOG = board.GP16
#OPTIC_SENSOR_DIGITAL = board.GP17

#async def catch_interrupt(pin):
#    """Print a message when pin goes low."""
#    with countio.Counter(pin) as interrupt:
#        while True:
#            if interrupt.count > 0:
#                interrupt.count = 0
#                #Put here: Script that counts the delta time between two pulses, and calculates the speed of a wheel based on a rotation ratio. 
#                # Onthoud: Je moet nog een onderdeel ontwerpen op de kart om de optische sensor te monteren, en zodat die werkt. 
#                # Ik dacht zelf om hier een LM393 te gebruiken. En dan een cirkel erdoorheen te laten draaien.
#                # Als je aan dit project bent begonnen, en dit bestand open hebt. Heb ik er wel vertrouwen in dat jij hier iets uit kan maken.
#                # Succes ermee en veel rijplezier! 
#            await asyncio.sleep(0)

#Gooi deze in je main code:
#async def main():
#    interrupt_task = asyncio.create_task(catch_interrupt(board.D3))
#    await asyncio.gather(interrupt_task)
#
#asyncio.run(main())
#-----------------------------------------------------------------------------

#Verklaar de verschillende busses voor de onderdelen.
SPIBus = busio.SPI(board.GP6,board.GP7,board.GP8) #SPI Bus is voornamelijk voor het 3.5" TFT SPI LCD scherm van elegoo, maar ook voor de micro-SD-Kaart reader van SparkFun. 
I2CBus = busio.I2C(board.GP2,board.GP3) #I2C voor 9-DOF sensor (MPU-9250 van SparkFun) en RTC: DS3231
GPS_UART = busio.UART(GPS_UART_TX,GPS_UART_RX,baudrate=9600) #Omdat UART geen meerdere slaven support, moet je twee keer een bus definen. Deze is voor GPS (NEO-6M)
#HC 12 verklaring--------------------------------------------------------------
HC12_UART = busio.UART(HC_12_TX, HC_12_RX,baudrate=4800) 
#HC12 Uart, ik raad 4800bps aan. dat heeft een range van ongeveer 500 meter in perfecte omstandigheden, de maximale afstand op CP berghem is 250m van de tenten af.
#De tijd om ~70 bytes door te sturen is dan 0.047s, snel genoeg dus
#Het format voor de HC-12 communicatie:
#Time, Heading, Xa, Ya, Za, Ox, Oy, Oz, LATITUDE, LONGITUDE, Altitude, Satellite count, DeltaPosition, Speed
#The time is provided like this: 123523 which is 12 hours 35 minutes and 23 seconds
#Heading (provided in degrees with 1 degree precision e.g.: 123)
#Xa, Ya, Za, Ox, Oy, Oz. Are all a float which is a value of less than 100.0 (4 digits)
#Lattitude or longitude: example: 00831.54761
#Satellite amount: 1 or 2 digit number. Less than or equal to 99
#DeltaPosition: float, less than 50.0
#Altitude: float, less than 100.0
#Speed: float, less than 100.0
#--------------------------------------------------------------HC 12 verklaring


#Define the different modules used in this setup
SDCard = sdcardio.SDCard(SPIBus,SD_Select)
vfs = storage.VfsFat(SDCard)
storage.mount(vfs,'/sd')

AccelMeter = roboticsmasters_mpu9250.MPU9250(i2c_bus=I2CBus)
RTCModule = adafruit_ds3231.DS3231(I2CBus)
GPSModule = adafruit_gps.GPS(GPS_UART,debug=False)

display = ILI9341(SPIBus,cs=LCD_CS,dc=LCD_RS,rst=LCD_RESET,width=480,height=320)

RED = (255,0,0)
BLUE = (0,255,0)
GREEN = (0,0,255)

def ScreenTest():
    # Fill the screen red, green, blue, then black:
    for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        display.fill(color565(color))
    # Clear the display
    display.fill(0)
    # Draw a red pixel in the center.
    display.pixel(display.width // 2, display.height // 2, color565(255, 0, 0))
    # Pause 2 seconds.
    time.sleep(2)
    # Clear the screen a random color
    display.fill(
        color565(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    )
    # Pause 2 seconds.
    time.sleep(2)


def WriteData(RecordID):
    
    data_dict = GetData()
    OutputString = f"{data_dict['TimeStr']}/{data_dict['Heading']}/{data_dict['Ax']}/{data_dict['Ay']}/{data_dict['Az']}/{data_dict['Mx']}/{data_dict['My']}/{data_dict['Mz']}/{data_dict['Lati']}/{data_dict['Long']}/{data_dict['SatCount']}/{data_dict['Speed']}\n"
    with open(f'/sd/{RecordID}','a') as f:
        f.write(OutputString)
    HC12_UART.write(OutputString.encrypt())

def GetData():
    currentT = RTCModule.datetime
    TimeStr = '{}_{}_{}_{:02}:{:02}:{:02}'.format(currentT.tm_mon, currentT.tm_mday, currentT.tm_year, currentT.tm_hour, currentT.tm_min, currentT.tm_sec)
    
    Ax, Ay, Az = AccelMeter.acceleration
    Mx, My, Mz = AccelMeter.magnetic
    Heading = (math.degrees(math.atan2(My, Mx)) + 360) % 360

    Speed = GPSModule.speed_knots*1.852   #Snelheid in km/u
    Long = GPSModule.longitude
    Lati = GPSModule.latitude #Long en Latitude uit GPS halen.
    SatCount = GPSModule.satellites 
    
    data_dict = {
    'TimeStr': TimeStr,
    'Ax': Ax,
    'Ay': Ay,
    'Az': Az,
    'Mx': Mx,
    'My': My,
    'Mz': Mz,
    'Heading': Heading,
    'Speed': Speed,
    'Long': Long,
    'Lati': Lati,
    'SatCount': SatCount
    }
    
    return data_dict


NextPing = 0
DeltaPing = 0
Recording = False
RecordID = 0
CC = False
CCSpeed = 0
ThreadActive = False


def Pause_Start_Interrupt():
    global Recording, RecordID
    if Recording:
        Recording = False
        HC12_UART.write(f'Finished recording set {RecordID}'.encode())

    else:
        Recording = True
        filenames = listdir('/sd')
        highest = 0
        for x in filenames:
            number = x[:-4]
            if int(number) > highest:
                highest = number
        
        RecordID = highest
        HC12_UART.write(f'Started recording set {RecordID}'.encode())

interrupt_pin = digitalio.DigitalInOut(RecordingButton_pin)
interrupt_pin.switch_to_input(pull=digitalio.Pull.UP)
interrupt_pin.irq(trigger=digitalio.Edge.RISING, handler=Pause_Start_Interrupt)

def CruiseControlInterrupt():
    global CC,CCSpeed
    if CC:
        CC = False
        CruiseControlOUT.value = False
    
    else:
        CC = True
        CruiseControlOUT.value = True

CruiseControlButton = digitalio.DigitalInOut(CruiseControlButton_pin).switch_to_input(pull=digitalio.Pull.UP)
CruiseControlOUT = digitalio.DigitalInOut(CruiseControlOUT_pin).switch_to_output()

def Core2(RecordID, CruiseControl, CCSpeed=0):
    global ThreadActive
    ThreadActive = True
    data_dict = GetData()
    DateTimeDict = RTCModule.datetime
    TimeHHMMSS = f'{DateTimeDict.tm_hour}:{DateTimeDict.tm_min}:{DateTimeDict.tm_sec}'
    generatedImage = GUI_Generator.GenerateUI(data_dict['speed'],RecordID,TimeHHMMSS,data_dict['SatCount'],CruiseControl,CCSpeed)
    display.image(generatedImage)
    time.sleep(1)
    ThreadActive = False


while True:
    if not ThreadActive:
        SecondThread = _thread.start_new_thread(Core2,(RecordID,CC))

    if HC12_UART.in_waiting > 0:
        command = HC12_UART.readline()
        if command == 'Start':
            if not Recording:
                Pause_Start_Interrupt()
                HC12_UART.write("Start -> Enabled Recording\n".encode())
            else:
                HC12_UART.write("Start -> Already Enabled!\n".encode())
        
        if command == 'Stop':
            if Recording:
                Pause_Start_Interrupt()
                HC12_UART.write("Stop -> Disabled Recording\n".encode())
            else:
                HC12_UART.write("Stop -> Already Disabled!\n".encode())    

    if Recording:
        currentTime = RTCModule.datetime
        currentEpoch = time.mktime(currentTime)
        if NextPing > currentEpoch:
            WriteData(currentTime)
            NextPing = currentEpoch + DeltaPing
