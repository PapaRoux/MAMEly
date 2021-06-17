# import modules
import pygame
import math
import time
import os
from os import listdir
from os.path import isfile, join
import xml.etree.ElementTree as ET
import sys
import datetime
import operator

MAMElyPath = os.path.dirname(os.path.abspath(__file__))+"/"
os.chdir(MAMElyPath)

# set the default config file name. This can be overridden in commandline vars below
# (multiple screen sizes, or different skins or variables)

configFile= "config.xml"

# parse commandline args

if len(sys.argv) > 1:
    for i in range(len(sys.argv)):
        CL = sys.argv[i]
        # separate variable from value
        equalsPosition = CL.find("=")
        if equalsPosition > 0:
            variableName = CL[0:equalsPosition].strip()
            variableValue = CL[equalsPosition+1:].strip()
            # test for each variabe and assign value
            if variableName == "-config":        
                configFile = str(variableValue)
                
# timer class, returns elapsed time since timer was created                
                
class DelayTimer:
    def __init__(self, countdown):
        self.startTime = time.time()
        self.countdown = countdown
        
    def getElapsedTime(self):
        return time.time() - self.startTime
    
    def timeUp(self):
        if self.getElapsedTime() >= self.countdown:
            return True
        else:
            return False
    
# platform definition class                
                
class Platform:
    def __init__(self, name, folder, config, skin):
        self.name = name
        self.folder = folder
        self.config = config
        self.skin = skin
        
# rom class, contains all the same fields as the db        
        
class Rom:
    def __init__(self,name,description,genre,rating,favorite,ignore):
        self.name = name
        self.description = description
        self.genre = genre
        self.rating = rating
        self.favorite = favorite
        self.ignore = ignore
        
# text drawing class, pretty much just a function at this point        

class TextObject:
    def __init__(self,displayText,fontColor,shadowColor,shadowOn,font,size,truncateLength):
        self.displayText = displayText
        self.fontColor = fontColor
        self.shadowColor = shadowColor
        self.font = pygame.font.Font(platformPath+font,fontSize)
        self.size = size
        self.truncateLength = truncateLength
    
    def draw(self,x,y):
        text = self.displayText[0:self.truncateLength]    
        if shadowOn == True:
            renderText = self.font.render(text, True, self.shadowColor)            
            textRect = renderText.get_rect()
            textRect.center = (x-2,y-2)
            screen.blit(renderText, textRect)
            textRect.center = (x+2,y+2)
            screen.blit(renderText, textRect)            
            textRect.center = (x-2,y+2)
            screen.blit(renderText, textRect)
            textRect.center = (x+2,y-2)
            screen.blit(renderText, textRect)
        renderText = self.font.render(text, True, self.fontColor)
        textRect = renderText.get_rect()
        textRect.center = (x,y)    
        screen.blit(renderText, textRect) 
        
# wrapper for the text drawing class        
        
def showText(x,y,displayText,fontColor,shadowColor,shadowOn,font,size,truncateLength):
    textObject = TextObject(displayText,fontColor,shadowColor,shadowOn,font,size,truncateLength)
    textObject.draw(x,y)
    return

# convert hex codes to python color tuples
                
def hexToColor(colorAsHexString):
    try:
        hexRR = colorAsHexString[0:2]
        hexGG = colorAsHexString[2:4]
        hexBB = colorAsHexString[4:6]
        decRR = int('0x'+hexRR, base=16)
        decGG = int('0x'+hexGG, base=16)
        decBB = int('0x'+hexBB, base=16)                
        colorSet = (decRR, decGG, decBB)
    except:
        colorSet = (128, 128, 128)
    return(colorSet)

# dump internal rom list to XML

def dumpMAMElyXML(roms,romCount):
    date = datetime.datetime.now()
    
    # don't overwrite original file. Write to temp file then rename if successful

    f = open(platformPath+"MAMEly.xml.tmp", "w")
    
    # also dump straight text lists of favorites and ignores for portability and redundancy's sake. These files are never actually read back in by MAMEly
    
    f_fav = open(platformPath+"favorites.txt", "w")
    f_ign = open(platformPath+"ignore.txt", "w")
    
    # write XML header

    f.write("<?xml version=\"1.0\"?>\n")
    f.write("<menu>\n")
    f.write("  <header>\n")
    f.write("    <listname>MAMEly</listname>\n")
    f.write("    <lastlistupdate>{}</lastlistupdate>\n".format(date))
    f.write("    <listgeneratorversion>dumpMAMElyXML (MAMEly.py v3.0)</listgeneratorversion>\n")
    f.write("  </header>\n")
     
    # loop through rom list, write one XML node per rom 
     
    romCountIndex = 0
    for rom in roms.values():
        if rom.name != "":
            f.write("  <game name=\"{}\">\n".format(rom.name))
            f.write("     <description>{}</description>\n".format(rom.description))
            f.write("     <genre>{}</genre>\n".format(rom.genre))
            f.write("     <rating>{}</rating>\n".format(rom.rating))
            f.write("     <favorite>{}</favorite>\n".format(rom.favorite))
            f.write("     <ignore>{}</ignore>\n".format(rom.ignore))
            f.write("  </game>\n")
            
            # add rom name to favorites.txt
            
            if rom.favorite == 1:
                f_fav.write("{}\n".format(rom.name))
                
            # add rom name to ignore.txt
                
            if rom.ignore == 1:
                f_ign.write("{}\n".format(rom.name))
        romCountIndex += 1

    f.write("</menu>\n")
    f.close()    
    f_fav.close()
    f_ign.close()
    
    # verify that the count that came in equals the count that went out

    if romCount == romCountIndex:

        # before and after counts match, so rename existing .xml to .xml.old, rename .xml.tmp to .xml
    
        os.rename(platformPath+"MAMEly.xml",platformPath+"MAMEly.xml.old")
        os.rename(platformPath+"MAMEly.xml.tmp",platformPath+"MAMEly.xml")
    else:
        print("PANIC!")
        quit()
        
    return

# main config file contains screen size and platform definitions

def readMainConfig(configFile):

    screenX = 0
    screenY = 0
    
    platforms = []

    tree = ET.parse(MAMElyPath+configFile)    
        
    root = tree.getroot()

    # loop through XML nodes

    for child in root:
        
        # get screen size
        
        if child.tag == "screensize":
            screenX = child.attrib.get("screenX")
            screenY = child.attrib.get("screenY")   
        
        # get platform name, folder, and name of platform config file
        
        if child.tag == "platform":
            platformName = ""
            platformFolder = ""
            platformConfig = ""
            platformSkin = ""
            platformName = child.attrib.get('name')
            for grandchild in child:
                if grandchild.tag == "folder":
                    platformFolder = grandchild.text
                if grandchild.tag == "config":
                    platformConfig = grandchild.text
                if grandchild.tag == "skin":
                    platformSkin = grandchild.text
                    
            if platformName == "" or platformFolder == "" or platformConfig == "" or platformSkin == "":
                print("Platform definition error: {}".format(platformName))
                quit()
            platform = Platform(platformName, platformFolder, platformConfig, platformSkin)
            platforms.append(platform)
            
    if screenX == 0 or screenY == 0:
        print("Screen size not set in config.xml")
        quit()
        
    return screenX, screenY, platforms

# initialize the timers so they already exist at first check

eventWait = DelayTimer(0)
joystickTimer = DelayTimer(0)
newJoystickTimer = True

# set a few delay time values 

executeDelayTime = 0.5
joystickDelayTime = 0.5
nextPlatformDelayTime = 0.25
nextGenreDelayTime = 0.25

# read the main config file

(screenX, screenY, platforms) = readMainConfig(configFile)

# create a pygame area

pygame.init()

# set up the joysticks

joystickDevice = []
joystickCount = pygame.joystick.get_count()

for joystickNumber in range(joystickCount):
    joystickDevice.append(pygame.joystick.Joystick(joystickNumber))
    joystickDevice[joystickNumber].init()        

# make keys repeat

pygame.key.set_repeat(500, 50)

# clock is used to manage how fast the screen updates

clock = pygame.time.Clock()

# video mode flags 

flags = pygame.SCALED

# Set the width and height of the screen [width, height]

size = (int(screenX), int(screenY))   

#create window surface

screen = pygame.display.set_mode(size,flags)
pygame.display.set_caption("MAMEly Emulator Launcher")    

# initialize some main loop variables

done = False
nextPlatform = False
platformNum = 0

# main loop, loops when a new platform is chosen
      
while not done:        

    # increment platform

    if nextPlatform == True:
        platformNum += 1
        
    # wrap around to first platform
        
    if platformNum >= len(platforms):
        platformNum = 0
    
    # set platform parameters
    
    platformPath = MAMElyPath + "platforms/" + platforms[platformNum].folder + "/"
    platformConfigFile = platformPath + platforms[platformNum].config
    platformSkinFile = platformPath + platforms[platformNum].skin

    # read platform config file 
        
    if platformConfigFile == "":
        print("ERROR: no config file specified")
        quit()
        
    f = open(platformConfigFile, "r")
    for textline in f:
        textline = textline.strip()
        # separate variable from value
        equalsPosition = textline.find("=")
        if equalsPosition > 0:
            variableName = textline[0:equalsPosition].strip()
            variableValue = textline[equalsPosition+1:].strip()      
            
            # test for each variabe and assign value

            if  variableName == "emulatorExecutable":
                emulatorExecutable = variableValue
            elif variableName == "romExtension":
                romExtension = variableValue
            elif variableName == "snapExtension":
                snapExtension = variableValue            
            elif variableName == "emulatorBasePath":
                emulatorBasePath = variableValue            
            elif variableName == "romSnapDirectory":
                romSnapDirectory = variableValue
            elif variableName == "romDirectory":
                romDirectory = variableValue
            elif variableName == "MAMElyxmlPath":
                MAMElyxmlPath = variableValue        
            elif variableName == "favoritesDirectory":
                favoritesDirectory = variableValue            
            elif variableName == "showXMLprogressBar":
                if variableValue == "True":
                    showXMLprogressBar = True 
                else:
                    showXMLprogressBar = False
            elif variableName == "compareXMLtoRoms":
                if variableValue == "True":
                    compareXMLtoRoms = True 
                else:
                    compareXMLtoRoms = False            
                
    f.close()   



    # read platform skin file 
        
    if platformSkinFile == "":
        print("ERROR: no skin file specified")
        quit()
        
    f = open(platformSkinFile, "r")
    for textline in f:
        textline = textline.strip()
        # separate variable from value
        equalsPosition = textline.find("=")
        if equalsPosition > 0:
            variableName = textline[0:equalsPosition].strip()
            variableValue = textline[equalsPosition+1:].strip()      
            
            # test for each variabe and assign value

            if   variableName == "backgroundImage":
                backgroundImage = variableValue
            elif variableName == "romListDisplayAreaX1":
                romListDisplayAreaX1 = int(variableValue)
            elif variableName == "romListDisplayAreaY1":
                romListDisplayAreaY1 = int(variableValue)
            elif variableName == "romListDisplayAreaX2":
                romListDisplayAreaX2 = int(variableValue)
            elif variableName == "romListDisplayAreaY2":
                romListDisplayAreaY2 = int(variableValue)
            elif variableName == "romListDisplaySpacing":
                romListDisplaySpacing = int(variableValue)             
            elif variableName == "romListDisplayFont":
                romListDisplayFont = variableValue
            elif variableName == "romListDisplayFontSize":
                romListDisplayFontSize = int(variableValue)
            elif variableName == "romListDisplayTruncateLen":
                romListDisplayTruncateLen = int(variableValue)            
            elif variableName == "romGenreX1":
                romGenreX1 = int(variableValue)
            elif variableName == "romGenreY1":
                romGenreY1 = int(variableValue)
            elif variableName == "romGenreX2":
                romGenreX2 = int(variableValue)
            elif variableName == "romGenreY2":
                romGenreY2 = int(variableValue) 
            elif variableName == "romGenreFont":
                romGenreFont = variableValue
            elif variableName == "romGenreFontSize":
                romGenreFontSize = int(variableValue)
            elif variableName == "romGenreTruncateLen":
                romGenreTruncateLen = int(variableValue)     
            elif variableName == "genreRatingOffset":
                genreRatingOffset = int(variableValue)     
            elif variableName == "messageFont":
                messageFont = variableValue
            elif variableName == "messageFontSize":
                messageFontSize = int(variableValue)
            elif variableName == "messageLen":
                messageLen = int(variableValue)
            elif variableName == "messageTime":
                messageTime = int(variableValue)  
            elif variableName == "messageTruncateLen":
                messageTruncateLen = int(variableValue)            
            elif variableName == "genreSetX1":
                genreSetX1 = int(variableValue)
            elif variableName == "genreSetY1":
                genreSetY1 = int(variableValue)  
            elif variableName == "genreSetX2":
                genreSetX2 = int(variableValue)  
            elif variableName == "genreSetY2":
                genreSetY2 = int(variableValue)    
            elif variableName == "genreSetFont":
                genreSetFont = variableValue
            elif variableName == "genreSetFontSize":
                genreSetFontSize = int(variableValue)
            elif variableName == "genreSetTruncateLen":
                genreSetTruncateLen = int(variableValue)             
            elif variableName == "romSnapX1":
                romSnapX1 = int(variableValue)
            elif variableName == "romSnapY1":
                romSnapY1 = int(variableValue)  
            elif variableName == "romSnapX2":
                romSnapX2 = int(variableValue)  
            elif variableName == "romSnapY2":
                romSnapY2 = int(variableValue)                
            elif variableName == "romCountX1":
                romCountX1 = int(variableValue)
            elif variableName == "romCountY1":
                romCountY1 = int(variableValue)  
            elif variableName == "romCountX2":
                romCountX2 = int(variableValue)  
            elif variableName == "romCountY2":
                romCountY2 = int(variableValue)          
            elif variableName == "romCountFont":
                romCountFont = variableValue
            elif variableName == "romCountFontSize":
                romCountFontSize = int(variableValue)
            elif variableName == "romCountTruncateLen":
                romCountTruncateLen = int(variableValue)             
            elif variableName == "romFileNameDisplayBoxX1":
                romFileNameDisplayBoxX1 = int(variableValue)
            elif variableName == "romFileNameDisplayBoxY1":
                romFileNameDisplayBoxY1 = int(variableValue)  
            elif variableName == "romFileNameDisplayBoxX2":
                romFileNameDisplayBoxX2 = int(variableValue)  
            elif variableName == "romFileNameDisplayBoxY2":
                romFileNameDisplayBoxY2 = int(variableValue)   
            elif variableName == "romFileNameDisplayBoxFont":
                romFileNameDisplayBoxFont = variableValue
            elif variableName == "romFileNameDisplayBoxFontSize":
                romFileNameDisplayBoxFontSize = int(variableValue)
            elif variableName == "romFileNameDisplayBoxTruncateLen":
                romFileNameDisplayBoxTruncateLen = int(variableValue)            
            elif variableName == "romGenreShadow":
                if variableValue == "True":
                    romGenreShadow = True 
                else:
                    romGenreShadow = False
            elif variableName == "romCountShadow":
                if variableValue == "True":
                    romCountShadow = True 
                else:
                    romCountShadow = False    
            elif variableName == "romListDisplayHighlightShadow":
                if variableValue == "True":
                    romListDisplayHighlightShadow = True 
                else:
                    romListDisplayHighlightShadow = False
            elif variableName == "romListDisplayShadow":
                if variableValue == "True":
                    romListDisplayShadow = True 
                else:
                    romListDisplayShadow = False                      
            elif variableName == "genreSetShadow":
                if variableValue == "True":
                    genreSetShadow = True 
                else:
                    genreSetShadow = False        
            elif variableName == "romFileNameShadow":
                if variableValue == "True":
                    romFileNameShadow = True 
                else:
                    romFileNameShadow = False   
            elif variableName == "messageShadow":
                if variableValue == "True":
                    messageShadow = True 
                else:
                    messageShadow = False  
                    
            elif variableName == "defaultHighlightFontForegroundColor":
                defaultHighlightFontForegroundColor = hexToColor(variableValue)
            elif variableName == "defaultFontForegroundColor":
                defaultFontForegroundColor = hexToColor(variableValue)
            elif variableName == "defaultTitleBarColor":
                defaultTitleBarColor = hexToColor(variableValue)
            elif variableName == "defaultTitleBarShadowColor":
                defaultTitleBarShadowColor = hexToColor(variableValue)
            elif variableName == "defaultRomCountColor":
                defaultRomCountColor = hexToColor(variableValue)            
            elif variableName == "defaultRomNameDisplayLineShadowColor":
                defaultRomNameDisplayLineShadowColor = hexToColor(variableValue)  
            elif variableName == "defaultRomNameDisplayLineHighlightShadowColor":
                defaultRomNameDisplayLineHighlightShadowColor = hexToColor(variableValue)  
            elif variableName == "defaultRomNameDisplayBoxShadowColor":
                defaultRomNameDisplayBoxShadowColor = hexToColor(variableValue)  
            elif variableName == "defaultTitleBarShadowColor":
                defaultTitleBarShadowColor = hexToColor(variableValue)  
            elif variableName == "defaultRomCountShadowColor":
                defaultRomCountShadowColor = hexToColor(variableValue)
            elif variableName == "defaultMessageColor":
                defaultMessageColor = hexToColor(variableValue)  
            elif variableName == "defaultGameSetBarColor":
                defaultGameSetBarColor = hexToColor(variableValue)              
            elif variableName == "defaultGameSetBarShadowColor":
                defaultGameSetBarShadowColor = hexToColor(variableValue)
            elif variableName == "defaultRomNameDisplayBoxColor":
                defaultRomNameDisplayBoxColor = hexToColor(variableValue)
            elif variableName == "defaultRomFileNameShadowColor":
                defaultRomFileNameShadowColor = hexToColor(variableValue)            
            elif variableName == "defaultRomFileNameColor":
                defaultRomFileNameColor = hexToColor(variableValue)      
                
    f.close()  















    
    # initialize flag/skip dictionaries
    
    flagsRomNameArray = []
    flagsRomValueArray = []
    skipGenreValues = {}
    skipRatingValues = {}
    
    # read rom flags (passed to emulator at runtime)
    
    try:
        f = open(platformPath+"_flags.txt", "r")
        for textline in f:
            if textline.find("#") == -1:
                textline = textline.strip()
                # separate variable from value
                equalsPosition = textline.find("=")
                if equalsPosition > 0:
                    flagsRomName = textline[0:equalsPosition].strip()
                    flagsRomValue = textline[equalsPosition+1:].strip()
                    flagsRomNameArray.append(flagsRomName)
                    flagsRomValueArray.append(flagsRomValue)
        f.close()
    except:
        null = 0

    # read list of genres to not show
    
    try:
        f = open(platformPath+"_skipGenre.txt", "r")
        for textline in f:
            if textline.find("#") == -1:    
                textline = textline.strip()
                skipGenreValues[textline] = 1
        f.close()
    except:
        null = 0
    
    # read list of ratings to not show
    
    try:
        f = open(platformPath+"_skipRating.txt", "r")
        for textline in f:
            if textline.find("#") == -1:    
                textline = textline.strip()
                skipRatingValues[textline] = 1
        f.close()
    except: 
        null = 0

    # calculate display area details from config values    

    romListDisplayVertOffset = 1
    romListDisplayVertSize = romListDisplayAreaY2 - romListDisplayAreaY1
    romListDisplayNumLines = int(romListDisplayVertSize / romListDisplaySpacing)
    romListDisplayNumLinesMiddle = round(romListDisplayNumLines/2)    
    romListDisplayAreaXCenter = int((romListDisplayAreaX2 - romListDisplayAreaX1)/2)+romListDisplayAreaX1
    romListDisplayAreaYCenter = int((romListDisplayAreaY2 - romListDisplayAreaY1)/2)+romListDisplayAreaY1

    romGenreXCenter = int((romGenreX2 - romGenreX1)/2)+romGenreX1
    romGenreYCenter = int((romGenreY2 - romGenreY1)/2)+romGenreY1

    romFileNameDisplayBoxXCenter = int((romFileNameDisplayBoxX2 - romFileNameDisplayBoxX1)/2)+romFileNameDisplayBoxX1
    romFileNameDisplayBoxYCenter = int((romFileNameDisplayBoxY2 - romFileNameDisplayBoxY1)/2)+romFileNameDisplayBoxY1

    genreSetXCenter = int((genreSetX2 - genreSetX1)/2)+genreSetX1
    genreSetYCenter = int((genreSetY2 - genreSetY1)/2)+genreSetY1

    romSnapXCenter = int((romSnapX2 - romSnapX1)/2)+romSnapX1
    romSnapYCenter = int((romSnapY2 - romSnapY1)/2)+romSnapY1
        
    maxRomSnapWidth = romSnapX2 - romSnapX1
    maxRomSnapHeight = romSnapY2 - romSnapY1    

    romCountXCenter = int((romCountX2 - romCountX1)/2)+romCountX1
    romCountYCenter = int((romCountY2 - romCountY1)/2)+romCountY1

    # add base path to relative paths to make full paths

    if romSnapDirectory[0] != "/":    
        romSnapDirectory = emulatorBasePath + romSnapDirectory
    if romDirectory[0] != "/":    
        romDirectory = emulatorBasePath + romDirectory
    
    # define colors

    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    LIGHT_GREY = (170, 170, 170)
    MED_GREY = (128, 128, 128)
    DARK_GREY = (50, 50, 50)
    GREY = MED_GREY
    
    # define keycodes
    
    K_DOWN = 1073741905
    K_UP = 1073741906
    K_LEFT = 1073741904
    K_RIGHT = 1073741903
    K_PAGEDOWN = 1073741902
    K_PAGEUP = 1073741899
    K_ENTER = 13
    K_ESCAPE = 27
    K_TAB = 9
    K_D = 100
    K_E = 101
    K_F = 102
    K_I = 105
        
    # load the skin background
    
    backgroundImage = pygame.image.load(platformPath+backgroundImage)

    # display READING MAMELY.XML startup status message

    screen.blit(backgroundImage, (0,0))
    fontColor = defaultMessageColor 
    shadowOn = romListDisplayHighlightShadow
    shadowColor = defaultRomNameDisplayLineHighlightShadowColor
    x = romListDisplayAreaXCenter
    y = romListDisplayAreaYCenter
    font = romListDisplayFont
    fontSize = messageFontSize
    truncateLength = romListDisplayTruncateLen
    #showText("Reading MAMEly.xml",X,Y,fontColor,fontShadow,shadowColor,font,fontSize,truncateLength)
    showText(x,y,"Reading MAMEly.xml",fontColor,shadowColor,shadowOn,font,size,truncateLength)    
    X1 = romListDisplayAreaX1+int((romListDisplayAreaX2-romListDisplayAreaX1)*0.10)
    Y1 = romListDisplayAreaYCenter+romListDisplaySpacing*2
    X2 = romListDisplayAreaX2-int((romListDisplayAreaX2-romListDisplayAreaX1)*0.10)
    XfullLength = X2-X1
    Y2 = Y1

    # update screen

    pygame.display.flip()

    # read MAMEly.xml file
        
    tree = ET.parse(platformPath+"MAMEly.xml")    
        
    root = tree.getroot()

    totalNodes = len(list(root))
    XMLromObjects = {}
    romRatings = {}
    romGenres = {}

    nodeCount = 0
    lastPct = -1
    numRomsFound = 0
    numRomsNotFound = 0
    xmlParsedArray = []

    # read each XML node

    for child in root:
        nodeCount += 1
        
        # calculate % complete (rounded to 2 decimals)
        
        pct = round((nodeCount/totalNodes)*100)
        
        # update screen for each whole integer %
        
        if pct % 1 == 0:
            if pct != lastPct and pct >= 1:
                XpctLength = XfullLength * (pct/100)
                Xpct = X1 + XpctLength
                if showXMLprogressBar == True:
                    pygame.draw.line(screen, RED, [X1,Y1], [Xpct,Y2], 20)
                pygame.display.flip()
            lastPct = pct    
            
        # read rom attributes from game nodes    
            
        if child.tag == "game":    
            romName = child.attrib.get('name')
            romDescription = ""
            romGenre = ""
            romRating = ""
            romFavorite = 0
            romIgnore = 0
            for grandchild in child:
                if grandchild.tag == "description":
                    romDescription = grandchild.text.title()
                try:
                    if grandchild.tag == "genre":
                        romGenre = grandchild.text.title()
                        slashPos = romGenre.find("/")
                        if slashPos > 0:
                            romGenre = XMLromGenre[0:slashPos].strip()
                except:                     
                    null = 0                    
                try:
                    if grandchild.tag == "rating":
                        romRating = grandchild.text
                except: 
                    null = 0
                try:
                    if grandchild.tag == "favorite":
                        romFavorite = int(grandchild.text)
                except: 
                    null = 0  
                try:
                    if grandchild.tag == "ignore":
                        romIgnore = int(grandchild.text)
                except: 
                    null = 0  
                    
            skipRom = False
            
            # see if this genre gets skipped
            
            try:
                if skipGenreValues[romGenre] == 1:
                    skipRom = True
            except:
                null = 0
                
            # hardcoded skip for all "TTL" mame roms (there's a bunch, and none are playable games)
                
            if romGenre.find("Ttl -") >= 0:
                skipRom = True
            
            # see if this rating gets skipped
            
            try:
                if skipRatingValues[romRating] == 1:
                    skipRom = True
            except:
                null = 0                
                
            # chekc for null genre or null rating    
                
            if romRating == "" or romRating == None:
                romRating = "General"
            if romGenre ==  "" or romGenre == None:
                romGenre = "General"
                         
            if skipRom == False:
                
                # make a rom object and store it in the rom dictionary
                
                romObject = Rom(romName,romDescription,romGenre,romRating,romFavorite,romIgnore)
                XMLromObjects[romName] = romObject
                
                # store the genre in the genre dictionary (unless it's GENERAL, we don't want a GENERAL list)
                
                if romGenre != "General":
                    romGenres[romGenre] = 1
                    
                # store the rating in the rating dictionary (unless it's GENERAL, we don't want a GENERAL list)                    
                    
                if romRating != "General":
                    
                    # prepend ratings with "__" so they sort to the end when added to genre list
                    
                    romGenres["__Rating: "+romRating] = 1

    # build an iterable genre array from the genre dictionary

    romGenreArray = []

    for romGenre in (sorted(romGenres.keys())):
        
        # remove the "__" from ratings once the sort is done
        
        if romGenre.find("__") == 0:
            romGenre = romGenre[2:]
        romGenreArray.append(romGenre)
        
    # put "ALL GAMES" and "FAVORITES" at the start of the genre array
        
    romGenreArray.insert(0,"Favorites")
    romGenreArray.insert(0,"All Games")
    romGenreArray.append("Ignore")
    
    # display startup READING ROM DIRECTORY status message

    screen.blit(backgroundImage, (0,0))
    fontColor = defaultMessageColor
    shadowOn = romListDisplayHighlightShadow
    shadowColor = defaultRomNameDisplayLineHighlightShadowColor
    x = romListDisplayAreaXCenter
    y = romListDisplayAreaYCenter
    font = romListDisplayFont
    fontSize = messageFontSize
    truncateLength = romListDisplayTruncateLen
    showText(x,y,"Reading ROM directory",fontColor,shadowColor,shadowOn,font,size,truncateLength)
    
    # update screen
    
    pygame.display.flip()

    # if comparing XML vs directoy, read rom directory directly to find existing roms

    if compareXMLtoRoms == True:
        romObjects = {}
        dirList = {}
        found = 0
        for f in os.listdir(romDirectory):
            
            # check for rom files, if file, remove rom extension
            
            if os.path.isfile(os.path.join(romDirectory, f)):
                extensionPos = f.find(romExtension)
                if extensionPos >= 0:
                    f = f[0:extensionPos]
            
            # check for rom subdirectories, but there's nothing to be done here
            
            elif os.path.isdir(os.path.join(romDirectory, f)):
                null = 0
                
            # if this rom exists in the XML list, add it to the rom array
                
            try:
                if XMLromObjects[f] != None:
                    romObjects[f] = XMLromObjects[f]
                    found = 1
            except:
                null = 0
            try:
                # if not found in XML without extension, try with
                if found == 0:
                    f = f + romExtension
                    if XMLromObjects[f] != None:
                        romObjects[f] = XMLromObjects[f]
            except:
                null = 0            
                
    else:
        
        # if not comparing, just copy the existing XML array to the main rom array
        
        romObjects = XMLromObjects.copy()

    """
    # import MAMEly 2.0 favorites
    
    tree = ET.parse(platformPath+"favorites.xml")
    root = tree.getroot()

    for child in root:
        if child.tag == "game":
            romFileName = child.attrib.get('name')
            if romFileName is not None:
                try:
                    romObjects[romFileName].favorite = 1
                except:
                    null = 0
    """
    
    # this string gets displayed in genre/rating area anytime it's not empty. Duration in config file.
    
    message = ""
    messageStartTime = 0

    # bit of weirdness with pygame key events, if the action taken after an event is read takes longer than the
    # key repeat time (currently 500ms), then there's multiple key events waiting to be read upon return
    # so I built a timer, and any events waiting during that time can be ignored. Otherwise, the action repeats
    # as the multiple events are read

    if nextPlatform == True:
        eventWait = DelayTimer(nextPlatformDelayTime)
        
    nextPlatform = False
    
    # force first read of genreSet
    
    readGenre = True
    
    # these values doesn't matter yet, the variables just need to be defined before entering the loop
    
    readFavorites = False
    readIgnore = False
    
    # start with game set = all games
    
    currentGenre = 0
    
    romNum = 0
    
    # main event loop, loop until user presses ESCAPE and done is set to True
    
    while not done and not nextPlatform:

        # if necessary, make a new array for the newly selected genre (also do this if added or removed a favorite)
        
        if readGenre == True or readFavorites == True or readIgnore:
            readGenre = False
            genreSet = []
                
            for romObject in (sorted(romObjects.values(), key=operator.attrgetter('description'))):
                
                # if genre is ALL GAMES then every rom makes it into array
                
                if romGenreArray[currentGenre] == "All Games":
                    if romObject.ignore == 0:
                        genreSet.append(romObject)
                    
                # if genre is FAVORITES then just check the FAVORITE attribute    
                    
                elif romGenreArray[currentGenre] == "Favorites":
                    if romObject.favorite == 1:
                        genreSet.append(romObject)
                        
                elif romGenreArray[currentGenre] == "Ignore":
                    if romObject.ignore == 1:
                        genreSet.append(romObject)
                        
                # otherwise check that the genre matches
                        
                elif romObject.genre == romGenreArray[currentGenre]:
                    if romObject.ignore == 0:
                        genreSet.append(romObject)
        
            numRoms = len(genreSet)
            
            # if reading a new genre (not add/remove favorite or ignore), start at the top of the rom list
            
            if readFavorites == False and readIgnore == False:
                romNum = 0
                
            readFavorites = False
            readIgnore = False
                
            # add blank space at top and bottom of scrolling list so selection is always in the middle of the screen
            
            for num in range(0,numRoms+romListDisplayNumLines):
                if num<romListDisplayNumLinesMiddle:
                    genreSet.insert(0,Rom("","","","","",""))
                if num>numRoms+romListDisplayNumLinesMiddle:       
                    genreSet.append(Rom("","","","","",""))        
            
        # read the josticks, store the values in dictionaries so they can be read through all at once
        
        joyControls = {}
        joysticks = {}
        
        for joystickNumber in range(joystickCount):

            joystick = joystickDevice[joystickNumber]
            
            joyControls['left_right'] = joystick.get_axis(0)
            joyControls['up_down'] = joystick.get_axis(1)
            joyControls['hat_left_right'] = joystick.get_hat(0)[0]
            joyControls['hat_up_down'] = joystick.get_hat(0)[1]
            
            joyControls['button0'] = joystick.get_button(0)
            joyControls['button1'] = joystick.get_button(1)
            joyControls['button2'] = joystick.get_button(2)
            joyControls['button3'] = joystick.get_button(3)
            
            joysticks[joystickNumber] = joyControls.copy()
        
        # iterate through the joystick values stored above
        
        joy_up = False
        joy_down = False
        joy_left = False
        joy_right = False
        joy_button0 = False
        joy_button1 = False
        joy_button2 = False
        joy_button3 = False
        
        for i in joysticks.keys():
            
            if joysticks[i]['up_down'] < -0.5 or joysticks[i]['hat_up_down'] > 0.5:
                joy_up = True
            if joysticks[i]['up_down'] > 0.5 or joysticks[i]['hat_up_down'] < -0.5:
                joy_down = True
            if joysticks[i]['left_right'] < -0.5 or joysticks[i]['hat_left_right'] < -0.5:
                joy_left = True
            if joysticks[i]['left_right'] > 0.5 or joysticks[i]['hat_left_right'] > 0.5:
                joy_right = True
            if joysticks[i]['button0'] == 1:
                joy_button0 = True
            if joysticks[i]['button1'] == 1:
                joy_button1 = True
            if joysticks[i]['button2'] == 1:
                joy_button2 = True
            if joysticks[i]['button3'] == 1:
                joy_button3 = True
        
        # none of the following commented code currently works
        
        # replicate the delay/repeat functionality of a keyboard, but for joystick
        
        # if not joystick nav right now, set the NEXT delay time to 0.5 sec, and turn off the current timer
        if joy_up == False and joy_down == False and joy_left == False and joy_right == False:
            joystickDelay = joystickDelayTime
            joystickTimer = DelayTimer(0)
        
        # if joystick nav and the timer is up, then we need to set a timer to either 0 or joystickDelayTime, as determined above
        if (joy_up == True or joy_down == True or joy_left == True or joy_right == True) and joystickTimer.timeUp() == True:
            joystickTimer = DelayTimer(joystickDelay)
            # now that a new timer is set, next one is set to 0, until above logic resets it to 0.5
            joystickDelay = 0
            newJoystickTimer = True
        
        # if the timer is not up, set all joy nav to false (except for the first push, just like with a keyboard first press before repeart)
        if joystickTimer.timeUp() == False and newJoystickTimer == False:
            joy_up = False
            joy_down = False
            joy_left = False
            joy_right = False
            
        newJoystickTimer = False
        
            
        # read the keyboard
        
        key_up = False
        key_down = False
        key_left = False
        key_right = False
        key_e = False
        key_f = False
        key_i = False
        key_tab = False
        key_enter = False
        key_escape = False
        
        for event in pygame.event.get():
            
            # if user clicks CLOSE WINDOW then set done = True
            
            if event.type == pygame.QUIT:
                done = True
                
            # no action to take when a key is released, but I left the event check in for the hell of it
                
            elif event.type == pygame.KEYUP:
                null = 0
                
            # if a key is pressed, read it    
                
            elif event.type == pygame.KEYDOWN: 
                #print(event.key)
                if event.key == K_DOWN:
                    key_down = True
                elif event.key == K_UP:
                    key_up = True
                elif event.key == K_RIGHT:
                    key_right = True
                elif event.key == K_LEFT:
                    key_left = True
                elif event.key == K_E:
                    key_e = True
                elif event.key == K_F:
                    key_f = True
                elif event.key == K_I:
                    key_i = True
                elif event.key == K_TAB:
                    key_tab = True
                    pygame.event.clear()
                elif event.key == K_ENTER:
                        key_enter = True
                elif event.key == K_ESCAPE:
                    key_escape = True
                    
        # set navigation values based on either keyboard or joystick values
                    
        nav_up = key_up or joy_up
        nav_down = key_down or joy_down
        nav_left = key_left or joy_left
        nav_right = key_right or joy_right
        nav_platform = key_e or joy_button2
        nav_favorite = key_f or joy_button3
        nav_genre = key_tab or joy_button1
        nav_ignore = key_i
        nav_run = key_enter or joy_button0
        nav_exit = key_escape
                    
        # and do the things accordingly
                    
        if nav_down == True:
            romNum += 1
        elif nav_up == True:
            romNum -= 1
        elif nav_right == True:
            romNum += romListDisplayNumLines
        elif nav_left == True:
            romNum -= romListDisplayNumLines
        elif nav_platform == True:
            if eventWait.timeUp():                  
                nextPlatform = True
        elif nav_favorite == True:
            if romGenreArray[currentGenre] == "Favorites":
                if genreSet[romExecNum].name != "":
                    try:
                        romObjects[romExecName].favorite = 0
                    except:
                        # if not found without extension, try with
                        romObjects[romExecName+romExtension].favorite = 0                                
                    message = romExecName[0:min(len(romExecName),20)] + " removed from Favorites"
                    dumpMAMElyXML(romObjects,len(romObjects))
                    readFavorites = True
            else:
                if genreSet[romExecNum].favorite == 1:
                    message = romExecName[0:min(len(romExecName),20)] + " already in Favorites"
                else:
                    if genreSet[romExecNum].name == None or genreSet[romExecNum].name == "":
                        print("Empty")
                        quit()
                    try:
                        romObjects[romExecName].favorite = 1
                    except:
                        # if not found without extension, try with
                        romObjects[romExecName+romExtension].favorite = 1                            
                    message = romExecName[0:min(len(romExecName),20)] + " added to Favorites"
                    dumpMAMElyXML(romObjects,len(romObjects))
                    readFavorites = True
        elif nav_ignore == True:
            if romGenreArray[currentGenre] == "Ignore":
                if genreSet[romExecNum].name != "":
                    try:
                        romObjects[romExecName].ignore = 0
                    except:
                        # if not found without extension, try with
                        romObjects[romExecName+romExtension].ignore = 0                                
                    message = romExecName[0:min(len(romExecName),20)] + " removed from Ignore List"
                    dumpMAMElyXML(romObjects,len(romObjects))
                    readIgnore = True
            else:
                if genreSet[romExecNum].ignore == 1:
                    message = romExecName[0:min(len(romExecName),20)] + " already in Ignore List"
                else:
                    if genreSet[romExecNum].name == None or genreSet[romExecNum].name == "":
                        print("Empty")
                        quit()
                    try:
                        romObjects[romExecName].ignore = 1
                    except:
                        # if not found without extension, try with
                        romObjects[romExecName+romExtension].ignore = 1                            
                    message = romExecName[0:min(len(romExecName),20)] + " added to Ignore List"
                    dumpMAMElyXML(romObjects,len(romObjects))
                    readIgnore = True
                    
        elif nav_genre == True:
            if eventWait.timeUp():                
                # don't attempt to change genres for another 0.25 seconds after genre change
                currentGenre += 1
                if currentGenre >= len(romGenreArray):
                    currentGenre = 0
                # reset timer
                eventWait = DelayTimer(nextGenreDelayTime)
                readGenre = True                        
        elif nav_run == True:
            if eventWait.timeUp():
                # don't attempt to execute a rom for another 0.5 seconds after emulator exit
                rom_fullpath = romDirectory+romExecName
                # if about to run a game, find any flags in the flag array
                try:
                    flagsArrayIndex = flagsRomNameArray.index(romExecName)
                except:
                    flagsArrayIndex = -1
                flags = ""
                if flagsArrayIndex >= 0:
                    flags = flagsRomValueArray[flagsArrayIndex]
                # run mame + flags + rom filename                  
                osCommand = emulatorExecutable+" "+flags+" "+"\""+rom_fullpath+romExtension+"\""
                os.system(osCommand)
                
                # reset timer
                eventWait = DelayTimer(executeDelayTime)
        elif nav_exit == True:
            done = True
            

        # wrap around list top and bottom
        
        if romNum > len(genreSet)-romListDisplayNumLines:
            #romNum = len(genreSet)-romListDisplayNumLines                
            romNum = 0       
            
        if romNum < 0:
            #romNum = 0            
            romNum = len(genreSet)-romListDisplayNumLines                                
                
        # get rid of the ZIP extension, so romname can be used for snap PNG as well
        romName = genreSet[romNum].name
        #romName = romName.replace(".zip","")
                                
        # --- Start with background image
        
        screen.blit(backgroundImage, (0,0))
    
        # --- Drawing code starts here

        # show genreset name
        fontColor = defaultGameSetBarColor
        shadowColor = defaultGameSetBarShadowColor
        shadowOn = genreSetShadow
        x = genreSetXCenter
        y = genreSetYCenter
        font = genreSetFont
        fontSize = genreSetFontSize
        truncateLength = genreSetTruncateLen
        
        if romGenreArray[currentGenre] != "All Games" and romGenreArray[currentGenre] != "Favorites" and romGenreArray[currentGenre] != "Ignore":
            showText(x,y,"Genre: "+romGenreArray[currentGenre],fontColor,shadowColor,shadowOn,font,size,truncateLength)
        else:
            showText(x,y,romGenreArray[currentGenre],fontColor,shadowColor,shadowOn,font,size,truncateLength)            

        # loop from current rom through all the roms that fit on the screen
        maxRomNum = min(romListDisplayNumLines+romNum,len(genreSet))
        for romListDisplayNum in range(romNum,maxRomNum):
            
            try:
                romName = genreSet[romListDisplayNum].name
            except:
                for rom in genreSet:
                    print("*{}*".format(rom.name))
                print(romListDisplayNumLines+romNum)
                print(romListDisplayNum)
                print(len(genreSet))
                quit()
            romName = romName.replace(romExtension,"")   
            romFullName = genreSet[romListDisplayNum].description
                        
            # calculate where to display current rom name on screen
            romListDisplayY = (romListDisplayNum-romNum+romListDisplayVertOffset)*romListDisplaySpacing+romListDisplayAreaY1

            # draw rom full name in list
            shadowColor = defaultRomNameDisplayLineShadowColor
            shadowOn = romListDisplayShadow
            fontColor = defaultFontForegroundColor
            x = romListDisplayAreaXCenter
            y = romListDisplayY
            font = romListDisplayFont
            fontSize = romListDisplayFontSize
            truncateLength = romListDisplayTruncateLen            
            showText(x,y,romFullName,fontColor,shadowColor,shadowOn,font,size,truncateLength)    
            
            # do special things with the middle rom, it's the one that you see image for and run on ENTER

            if (romListDisplayNum - romNum) == romListDisplayNumLinesMiddle:
                # show this line in a different color
                fontColor = defaultHighlightFontForegroundColor 
                shadowOn = romListDisplayHighlightShadow
                shadowColor = defaultRomNameDisplayLineHighlightShadowColor
                x = romListDisplayAreaXCenter
                y = romListDisplayY
                font = romListDisplayFont
                fontSize = romListDisplayFontSize
                truncateLength = romListDisplayTruncateLen
            
                showText(x,y,romFullName,fontColor,shadowColor,shadowOn,font,size,truncateLength)    
                        
                # remember some things about this particular rom, because loop continues with more roms for bottom of list
                romExecName = romName
                romSnapName = romName
                romExecNum = romListDisplayNum
                romSnapFullPath1 = romSnapDirectory+romSnapName+snapExtension
                romSnapFullPath2 = romSnapDirectory+romSnapName+"/0000"+snapExtension
                
                # draw genre and rating in genre area
                
                romGenre = "Genre: "+genreSet[romExecNum].genre
                romRating = "Rating: "+genreSet[romExecNum].rating
                if numRoms == 0 and romGenreArray[currentGenre] == "Favorites":
                    romGenre = "You have no favorites"
                    romRating = "Add Favorite by pressing F in any other list"
                fontColor = defaultRomNameDisplayBoxColor
                shadowOn = romGenreShadow
                shadowColor = defaultGameSetBarColor
                x = romGenreXCenter
                y = romGenreYCenter-genreRatingOffset
                font = romGenreFont
                fontSize = romGenreFontSize
                truncateLength = romGenreTruncateLen
                if message == "":
                    showText(x,y,romGenre,fontColor,shadowColor,shadowOn,font,size,truncateLength)                        
                else:
                    fontColor = defaultMessageColor
                    font = messageFont
                    fontSize = messageFontSize
                    truncateLength = messageTruncateLen
                    showText(x,romGenreYCenter,message,fontColor,shadowColor,shadowOn,font,size,truncateLength)                        
                    if messageStartTime == 0:
                        messageStartTime = time.time()
                    else:
                        if time.time() - messageStartTime > messageTime:
                            message = ""
                            messageStartTime = 0
                
                fontColor = defaultRomNameDisplayBoxColor
                shadowOn = romGenreShadow
                shadowColor = defaultGameSetBarColor
                x = romGenreXCenter
                y = romGenreYCenter+genreRatingOffset
                font = romGenreFont
                fontSize = romGenreFontSize
                truncateLength = romGenreTruncateLen
                if message == "":
                    showText(x,y,romRating,fontColor,shadowColor,shadowOn,font,size,truncateLength)                        
                
                # show count "# of ###"
                FontShadowColor = defaultRomCountShadowColor
                shadowOn = romCountShadow
                fontColor = defaultRomCountColor
                romCountText = str(min(romNum+1,numRoms))+" of "+str(numRoms)
                x = romCountXCenter
                y = romCountYCenter
                font = romCountFont
                fontSize = romCountFontSize
                truncateLength = romCountTruncateLen
                showText(x,y,romCountText,fontColor,shadowColor,shadowOn,font,size,truncateLength)    
                
                # show rom file name (not full name) in file name area
                FontShadowColor = defaultRomFileNameShadowColor
                shadowOn = romFileNameShadow
                fontColor = defaultRomFileNameColor
                x = romFileNameDisplayBoxXCenter
                y = romFileNameDisplayBoxYCenter
                font = romFileNameDisplayBoxFont
                fontSize = romFileNameDisplayBoxFontSize
                truncateLength = romFileNameDisplayBoxTruncateLen
                showText(x,y,romName,fontColor,shadowColor,shadowOn,font,size,truncateLength)    
            
                # load rom snapshot image if available, otherwise load "image not available"
                
                try:
                    try:
                        romSnapFound = True        
                        romSnapImage = pygame.image.load(romSnapFullPath1) 
                    except:
                        romSnapFound = True        
                        romSnapImage = pygame.image.load(romSnapFullPath2)     
                except:
                    romSnapFound = False
                    romSnapImage = pygame.image.load(MAMElyPath+"/image_not_available.png") 
                
                # resize image width for uniform display
                
                wpercent = (maxRomSnapWidth / float(romSnapImage.get_size()[0]))
                newWidth = maxRomSnapWidth
                newHeight = int((float(romSnapImage.get_size()[1]) * float(wpercent)))
                romSnapImage = pygame.transform.scale(romSnapImage, (newWidth, newHeight))
                romImageWidth = romSnapImage.get_size()[0]
                romImageHeight = romSnapImage.get_size()[1]
                
                # if resized image is too tall for image area, resize for correct height instead
                
                if romImageHeight > maxRomSnapHeight:
                    hpercent = (maxRomSnapHeight / float(romSnapImage.get_size()[1]))
                    newWidth = int((float(romSnapImage.get_size()[0]) * float(hpercent)))
                    newHeight = maxRomSnapHeight
                    romSnapImage = romSnapImage = pygame.transform.scale(romSnapImage, (newWidth, newHeight))
                    romImageWidth = romSnapImage.get_size()[0]
                    romImageHeight = romSnapImage.get_size()[1]            
                
                # draw rom snap image on screen surface
                
                screen.blit(romSnapImage, (romSnapXCenter-int(romImageWidth/2),romSnapYCenter-int(romImageHeight/2)))
                        
        # update the screen

        pygame.display.flip()
            
        # limit to 60 frames per second        

        clock.tick(60)
  
# if done, close the window and quit

pygame.quit()
