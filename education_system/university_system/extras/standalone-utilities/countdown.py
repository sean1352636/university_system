import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime, timedelta

class CountdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Countdown Timer & Clock")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # Variables
        self.is_running = False
        self.is_paused = False
        self.remaining_time = 0
        self.mode = "timer"  # "timer" or "clock"
        
        # Configure styles
        self.setup_styles()
        
        # Create UI
        self.create_widgets()
        
        # Start the clock update
        self.update_clock()
    
    def setup_styles(self):
        """Configure custom styles for widgets"""
        style = ttk.Style()
        style.configure("Large.TLabel", font=("Arial", 48, "bold"))
        style.configure("Medium.TLabel", font=("Arial", 16))
        style.configure("Small.TLabel", font=("Arial", 12))
    
    def create_widgets(self):
        """Create all UI widgets"""
        # Mode selector
        mode_frame = tk.Frame(self.root, bg="#f0f0f0")
        mode_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(mode_frame, text="Mode:", font=("Arial", 12), bg="#f0f0f0").pack(side=tk.LEFT, padx=10)
        
        self.mode_var = tk.StringVar(value="timer")
        tk.Radiobutton(mode_frame, text="Countdown Timer", variable=self.mode_var, 
                      value="timer", command=self.switch_mode, font=("Arial", 10),
                      bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="Current Time", variable=self.mode_var, 
                      value="clock", command=self.switch_mode, font=("Arial", 10),
                      bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        # Display frame
        self.display_frame = tk.Frame(self.root, bg="white", relief=tk.SUNKEN, bd=2)
        self.display_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        # Time display
        self.time_label = tk.Label(self.display_frame, text="00:00:00", 
                                   font=("Arial", 60, "bold"), bg="white", fg="#2c3e50")
        self.time_label.pack(expand=True)
        
        # Date display (for clock mode)
        self.date_label = tk.Label(self.display_frame, text="", 
                                   font=("Arial", 14), bg="white", fg="#7f8c8d")
        
        # Input frame (for timer mode)
        self.input_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.input_frame.pack(pady=10)
        
        tk.Label(self.input_frame, text="Hours:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=0, padx=5)
        self.hours_var = tk.StringVar(value="0")
        self.hours_spin = tk.Spinbox(self.input_frame, from_=0, to=23, textvariable=self.hours_var, 
                                     width=5, font=("Arial", 12))
        self.hours_spin.grid(row=0, column=1, padx=5)
        
        tk.Label(self.input_frame, text="Minutes:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=2, padx=5)
        self.minutes_var = tk.StringVar(value="0")
        self.minutes_spin = tk.Spinbox(self.input_frame, from_=0, to=59, textvariable=self.minutes_var, 
                                       width=5, font=("Arial", 12))
        self.minutes_spin.grid(row=0, column=3, padx=5)
        
        tk.Label(self.input_frame, text="Seconds:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=4, padx=5)
        self.seconds_var = tk.StringVar(value="0")
        self.seconds_spin = tk.Spinbox(self.input_frame, from_=0, to=59, textvariable=self.seconds_var, 
                                       width=5, font=("Arial", 12))
        self.seconds_spin.grid(row=0, column=5, padx=5)
        
        # Control buttons
        self.button_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.button_frame.pack(pady=10)
        
        self.start_button = tk.Button(self.button_frame, text="Start", command=self.start_timer,
                                     font=("Arial", 12), bg="#27ae60", fg="white",
                                     width=10, height=2, cursor="hand2")
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.pause_button = tk.Button(self.button_frame, text="Pause", command=self.pause_timer,
                                     font=("Arial", 12), bg="#f39c12", fg="white",
                                     width=10, height=2, cursor="hand2", state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=5)
        
        self.reset_button = tk.Button(self.button_frame, text="Reset", command=self.reset_timer,
                                     font=("Arial", 12), bg="#e74c3c", fg="white",
                                     width=10, height=2, cursor="hand2")
        self.reset_button.grid(row=0, column=2, padx=5)
        
        # Status label
        self.status_label = tk.Label(self.root, text="Ready", font=("Arial", 10), 
                                     bg="#f0f0f0", fg="#7f8c8d")
        self.status_label.pack(pady=5)
        
        # Set initial mode
        self.switch_mode()
    
    def switch_mode(self):
        """Switch between timer and clock modes"""
        self.mode = self.mode_var.get()
        
        if self.mode == "clock":
            # Hide timer controls
            self.input_frame.pack_forget()
            self.button_frame.pack_forget()
            self.status_label.pack_forget()
            self.date_label.pack()
            
            # Reset timer state
            self.is_running = False
            self.is_paused = False
            
        else:  # timer mode
            # Show timer controls
            self.date_label.pack_forget()
            self.input_frame.pack(pady=10)
            self.button_frame.pack(pady=10)
            self.status_label.pack(pady=5)
            
            # Reset display
            if not self.is_running:
                self.time_label.config(text="00:00:00", fg="#2c3e50")
                self.status_label.config(text="Ready")
    
    def start_timer(self):
        """Start the countdown timer"""
        if not self.is_running:
            # Get time from spinboxes
            hours = int(self.hours_var.get())
            minutes = int(self.minutes_var.get())
            seconds = int(self.seconds_var.get())
            
            self.remaining_time = hours * 3600 + minutes * 60 + seconds
            
            if self.remaining_time <= 0:
                self.status_label.config(text="Please set a time greater than 0")
                return
            
            self.is_running = True
            self.is_paused = False
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.status_label.config(text="Running...")
            
            # Disable spinboxes
            self.hours_spin.config(state=tk.DISABLED)
            self.minutes_spin.config(state=tk.DISABLED)
            self.seconds_spin.config(state=tk.DISABLED)
            
            self.countdown()
    
    def pause_timer(self):
        """Pause or resume the timer"""
        if self.is_running:
            self.is_paused = not self.is_paused
            if self.is_paused:
                self.pause_button.config(text="Resume")
                self.status_label.config(text="Paused")
            else:
                self.pause_button.config(text="Pause")
                self.status_label.config(text="Running...")
                self.countdown()
    
    def reset_timer(self):
        """Reset the timer"""
        self.is_running = False
        self.is_paused = False
        self.remaining_time = 0
        
        self.time_label.config(text="00:00:00", fg="#2c3e50")
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="Pause")
        self.status_label.config(text="Ready")
        
        # Enable spinboxes
        self.hours_spin.config(state=tk.NORMAL)
        self.minutes_spin.config(state=tk.NORMAL)
        self.seconds_spin.config(state=tk.NORMAL)
    
    def countdown(self):
        """Update countdown timer"""
        if self.is_running and not self.is_paused:
            if self.remaining_time > 0:
                # Calculate hours, minutes, seconds
                hours = self.remaining_time // 3600
                minutes = (self.remaining_time % 3600) // 60
                seconds = self.remaining_time % 60
                
                # Update display
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.time_label.config(text=time_str)
                
                # Change color when time is running low
                if self.remaining_time <= 10:
                    self.time_label.config(fg="#e74c3c")  # Red
                elif self.remaining_time <= 60:
                    self.time_label.config(fg="#f39c12")  # Orange
                
                self.remaining_time -= 1
                
                # Schedule next update
                self.root.after(1000, self.countdown)
            else:
                # Timer finished
                self.time_label.config(text="00:00:00", fg="#e74c3c")
                self.status_label.config(text="Time's up!")
                self.is_running = False
                self.start_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                
                # Flash the display
                self.flash_display()
                
                # Play a beep (if available)
                try:
                    self.root.bell()
                except Exception:
                    pass
    
    def flash_display(self, count=0):
        """Flash the display when timer finishes"""
        if count < 6:
            current_bg = self.display_frame.cget("bg")
            new_bg = "#e74c3c" if current_bg == "white" else "white"
            self.display_frame.config(bg=new_bg)
            self.time_label.config(bg=new_bg)
            self.root.after(300, lambda: self.flash_display(count + 1))
        else:
            self.display_frame.config(bg="white")
            self.time_label.config(bg="white")
            
            # Enable spinboxes
            self.hours_spin.config(state=tk.NORMAL)
            self.minutes_spin.config(state=tk.NORMAL)
            self.seconds_spin.config(state=tk.NORMAL)
    
    def update_clock(self):
        """Update the current time display"""
        if self.mode == "clock":
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S")
            date_str = now.strftime("%A, %B %d, %Y")
            
            self.time_label.config(text=time_str, fg="#2c3e50")
            self.date_label.config(text=date_str)
        
        # Schedule next update
        self.root.after(1000, self.update_clock)

def main():
    root = tk.Tk()
    root.configure(bg="#f0f0f0")
    app = CountdownTimer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
