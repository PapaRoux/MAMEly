import os

# read catver.ini

romarray = []
genrearray = []
maturearray=[]

print("Reading catver.ini")

file1 = open('catver.ini', 'r')
 
inCategories = False
while True:
    # Get next line from file
    line = file1.readline()
    
    if line.find("[") >= 0:
        if line.find("[Category]") >= 0:
            inCategories = True
        else:
            inCategories = False
    
    if inCategories == True:
        if line.find("[Category]") == -1:
            line = line.strip() + ' / '
            if line != ' / ':       
                rompos = line.find('=')
                romname = line[0:rompos]
                genrestring = line[rompos+1:].replace("*","-")
                maturepos = genrestring.find('- Mature -')
                if maturepos >= 0:
                    mature = True
                else:
                    mature = False
                slashpos = genrestring.find(' / ')
                genre = genrestring[0:slashpos].replace("&","and")
                #print("{}:{}".format(romname,genre))
                romarray.append(romname)
                genrearray.append(genre)
                maturearray.append(mature)
 
    # if line is empty
    # end of file is reached
    if not line:
        break  
 
file1.close()

print("{} roms in catver.ini".format(len(romarray)))


print("Reading mame-listxml.xml")

import xml.etree.ElementTree as ET
try:
    tree = ET.parse('mame-listxml.xml')
except:
    print("\n\n\nCannot find mame-listxml.xml\n\n\n")
    quit()
    
root = tree.getroot()
totalNodes = len(list(root))

nodeCount = 0
lastPct = -1
numRomsFound = 0
numRomsNotFound = 0
xmlParsedArray = []

import datetime

date = datetime.datetime.now()

f = open("MAMEly.xml", "w")

f.write("<?xml version=\"1.0\"?>\n")
f.write("<menu>\n")
f.write("  <header>\n")
f.write("    <listname>MAMEly</listname>\n")
f.write("    <lastlistupdate>{}</lastlistupdate>\n".format(date))
f.write("    <listgeneratorversion>generateMAMElyXML v1.0</listgeneratorversion>\n")
f.write("  </header>\n")

for child in root:
    nodeCount += 1

    if child.tag == "machine":    
        romname = child.attrib.get('name')

        foundRom = True
            
        if foundRom == True:
            #print("found "+str(searchForXMLromName)) 
            description = ""
            year = ""
            manufacturer = ""
            for grandchild in child:
                if grandchild.tag == "description":
                    description = grandchild.text.title().replace("&","")
                try:
                    if grandchild.tag == "year":
                        year = grandchild.text
                except: 
                    null = 0

                try:
                    if grandchild.tag == "manufacturer":
                        manufacturer = grandchild.text.title()
                except: 
                    null = 0                    
    pct = round((nodeCount/totalNodes)*100)
    if pct % 1 == 0:
        if pct != lastPct and pct >= 1:
            lastPct = pct    
            print("Writing xml file ({}% complete)".format(pct))
    try:
        findrom = romarray.index(romname)
        #print("{},{},{},mature={}".format(romname,description,genrearray[findrom],maturearray[findrom]))
        if maturearray[findrom] == True:
            rating = "Rating: Mature"
        else:
            rating = "Rating: General"
        
        f.write("  <game name=\"{}\">\n".format(romname))
        f.write("     <description>{}</description>\n".format(description))
        f.write("     <genre>{}</genre>\n".format(genrearray[findrom]))
        f.write("     <rating>{}</rating>\n".format(rating))
#        f.write("     <manufacturer>{}</manufacturer>\n".format(manufacturer))
#        f.write("     <year>{}</year>\n".format(year))
        f.write("  </game>\n")
                       
    except:
        null = 0            

f.write("</menu>\n")

f.close()

quit()




