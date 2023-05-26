import busio, time, digitalio, sdcardio, board
from adafruit_rgb_display import color565
from adafruit_rgb_display.ili9341 import ILI9341
import roboticsmasters_mpu9250
import adafruit_ds3231, adafruit_gps

SDCardPin = board.GP14
SD_DetectPin = board.GP15
LCD_CS = board.GP9
TP_CS = board.GP10
LCD_RS = board.GP11
LCD_RESET = board.GP12

#Define SPI for SD Card and Screen, Define I2C for accel and RTC. And define UART for GPS module
SPIBus = busio.SPI(board.GP6,board.GP7,board.GP8)
I2CBus = busio.I2C(board.GP2,board.GP3)
UARTBus = busio.UART(board.GP0,board.GP1,baudrate=9600,timeout=30)

#Define the different modules used in this setup
SDCard = sdcardio.SDCard(SPIBus,SDCardPin)
AccelMeter = roboticsmasters_mpu9250.MPU9250(i2c_bus=I2CBus)
RTCModule = adafruit_ds3231.DS3231(I2CBus)
GPSModule = adafruit_gps.GPS(UARTBus,debug=False)
Display = ILI9341

