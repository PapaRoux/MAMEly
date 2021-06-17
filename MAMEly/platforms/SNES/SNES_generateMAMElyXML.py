import os
import datetime
romExtension = ".smc"
date = datetime.datetime.now()

f_out = open("MAMEly.xml","w")
f_in = open("romlist.txt","r")


f_out.write("<?xml version=\"1.0\"?>\n")
f_out.write("<menu>\n")
f_out.write("   <header>\n")
f_out.write("       <listname>MAMEly</listname>\n")
f_out.write("       <lastlistupdate>{}</lastlistupdate>\n".format(date))
f_out.write("       <listgeneratorversion>makeMAMEly-xml v1.0</listgeneratorversion>\n")
f_out.write("   </header>\n")


for textline in f_in:
    if textline.find(romExtension) >= 0:
        textline = textline.strip()
        textline = textline.replace("&","and")    
        textline = textline.replace("*","-")
        textline = textline.replace(romExtension,"")

        #f_out.write("   <game name=\"{}\">\n".format(textline)+romExtension)
        f_out.write("   <game name=\"{}\">\n".format(textline+romExtension))
        f_out.write("       <description>{}</description>\n".format(textline))
        f_out.write("       <genre>No Genre</genre>\n")
        f_out.write("       <rating>Rating: General</rating>\n")
        f_out.write("   </game>\n")
    
f_out.write("</menu>")
f_in.close()
f_out.close()


     
