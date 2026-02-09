'''
Python Program to Create Digital Clock
Author: Dr.Milan Parmar
'''

import tkinter as tk

from time import strftime

root = tk.Tk()

root.title("Digital clock")

def clock():
    tick = strftime("%H:%M:%S %p")

    label.config(text =tick)

    label.after(1000, clock)

label = tk.Label(root, font = ("segoe", 60), foreground = "yellow", background = "black")

label.pack(anchor= "center")

clock()
root.mainloop()