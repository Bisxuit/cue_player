#!/usr/bin/env python
#  Copyright 2017 Bisxuit

import sys,os,math,datetime
import pygame as pyg
import alsaaudio # give up on cross platform

# TODO - Edit cus file - edit mode (volume, fadeout, reorder, add, remove, comment/uncomment,save,load (icon))
# TODO - Global pause
# TODO - Sort out file paths
# TODO - Loop effects
# TODO - Loop list (e.g. music)
# TODO - Visual rep of sound file
# TODO - cue lib line in sidebar

class Player:
	def __init__(self,cue_sheet):
		pyg.mixer.pre_init(44100, -16, 2, 2048) # setup mixer to avoid sound lag
		pyg.init()
		
		self.cue_sheet = cue_sheet
		self.read_cue_sheet()
		self.running = False
		self.time_start = 0
		
		try:
			self.alsa = alsaaudio.Mixer()
			self.have_volume = True
		except:
			self.have_volume = False
				
		
	def read_cue_sheet(self):
		self.cues = []
		self.show_name = self.cue_sheet.split("/")[-1].replace(".cus","").replace("_"," ")
			
		i = 0
		for line in open(self.cue_sheet):
			if len(line.strip())==0:
				# Blank line
				continue
			elif line[0]=="#":
				# Comment line
				continue
			else:
				try:
					temp_n = line.split(",")[0].strip()
					temp_name = line.split(",")[1].strip()
					temp_filename = line.split(",")[2].strip()
					temp_fade_time = int(line.split(",")[3].strip()) #ms
					temp_volume = line.split(",")[4].strip()
				except:
					print "Bad line in "+self.cue_sheet+": "
					print "   "+line
					continue
			
			if not(self.add_cue(temp_n,temp_name,temp_filename,temp_fade_time,temp_volume,i)):
				print "Could not add cue ",line
			else:
				i+=1
			
		self.i = 0
		self.n = len(self.cues) # including dummy final cue
		self.add_last_cue(self.n)
		
			
	def add_cue(self,temp_n,temp_name,temp_filename,temp_fade_time,volume,i):
		c = Cue(temp_n,temp_name,temp_filename,temp_fade_time,volume,i)
		if c:
			self.cues.append(c)
			return 1
		else:
			# Failed
			return 0
	
	
	def add_last_cue(self,i):
		c = Cue(999,'END','END',0,0,i,dummy=True)
		if c:
			self.cues.append(c)
			return 1
		return 0
	
	
	def reset(self):
		self.stop_all()
		self.read_cue_sheet()
		self.running = False
		self.time_start = 0
		
				
	def play_selected(self):
		if self.i == self.n:
			# Dummy final cue - treat as fade all
			self.fadeout_all()
			return
		
		if not self.running:
			# First play
			self.running = True
			self.time_start = datetime.datetime.now()
			
		this_cue = self.cues[self.i]
		# Deactivate all other music cues (as only one MP3 can be loaded at a time)
		if not(this_cue.is_sound):
			for c in self.cues:
				if not(c.is_sound):
					c.active = False
					
		# TODO - check to see how many channels are active (could run out)
		this_cue.play()
		self.down()
	
	
	def fadeout_last(self):
		if self.i>0:
			self.cues[self.i-1].fadeout()
	
	
	def fadeout_all(self):
		for c in self.cues:
			if c.is_playing():
				c.fadeout()
				
					
	def up(self):
		self.i = max(0,self.i-1)
	
		
	def down(self):
		self.i = min(self.n,self.i+1)
	
	
	def stop_all(self):
		for c in self.cues:
			c.stop()
		pyg.mixer.music.stop()
	
	
	def unload(self,seq_num):
		for c in self.cues:
			if c.seq_num == seq_num:
				c.unload()
	
	
	def get_system_volume(self):
		vol = self.alsa.getvolume()
		return int(vol[0])


	def set_system_volume(self,change):
		vol = self.get_system_volume()
		vol = int(normalise(vol + change,100))
		self.alsa.setvolume(vol)
				
				
		
class Cue:
	def __init__(self,cue_number,name,filename,fade_time,volume,seq_num,dummy = False):
		self.cue_number = int(cue_number)
		self.filename = filename
		self.name = name
		
		if not dummy:
			self.is_dummy = False
			# Check if the sound effect exists and will actually play
			if os.path.isfile(self.filename):
				ext = filename[-3:].lower()
				if ext=="mp3":
					# Music - streamed from drive
					self.s = pyg.mixer.Sound(self.filename)
					from mutagen.mp3 import MP3
					audio = MP3(self.filename)
					self.length = audio.info.length #s
					self.is_sound = False
				elif ext=="ogg" or ext=="wav":
					# Proper sound with mixer and channels etc (loaded into memory)
					self.s = pyg.mixer.Sound(self.filename)
					self.length = self.s.get_length() #s
					self.is_sound = True
				else:
					print "File type not recognised: "+self.filename
					self.length = 0
					self.is_sound = False
			else:
				# Missing file
				self.length = 0
				self.is_sound = False
				print "File not found: "+self.filename
			
			# No volume means the cue is pointless
			if volume<=0:
				self.length = 0
				print "Zero volume: "+self.filename
		else:
			self.is_dummy = True
			self.length = 0
			self.is_sound = False
		
		self.volume = normalise(volume)
		self.channel = -1
		self.active = False
		self.played = False
		self.seq_num = seq_num
		self.fade_time = fade_time #ms
		self.fade_start_time = 0
		

	def play(self):
		# Prevent multiple versions of the same cue playing
		if not self.is_playing():
			if self.length == 0:
				# Missing file or dummy end sound cue
				pass
			elif self.is_sound:
				self.active = True
				self.s.set_volume(self.volume)
				self.channel = self.s.play()
				self.channel.set_endevent(pyg.USEREVENT+self.seq_num)
				self.time_play = pyg.time.get_ticks()
			else:
				pyg.mixer.music.load(self.filename)
				self.active = True
				pyg.mixer.music.set_volume(self.volume)
				pyg.mixer.music.play()
				pyg.mixer.music.set_endevent(pyg.USEREVENT+self.seq_num)
		
		self.played = True
		
		
	def fadeout(self):
		if self.is_playing:
			if self.is_sound:
				self.s.fadeout(self.fade_time)
			else:
				pyg.mixer.music.fadeout(self.fade_time)
			self.fade_start_time = pyg.time.get_ticks()
		
	
	def stop(self):
		if self.is_sound:
			self.s.stop()
		self.active = False
		
		
	def is_playing(self):
		if self.is_sound:
			temp = self.active and self.channel.get_busy()
		else:
			temp = self.active and pyg.mixer.music.get_busy()
		if not temp:
			self.fade_start_time = 0
		return temp
		

	def get_pos(self):
		if self.is_sound:
			# From timer
			l = ((pyg.time.get_ticks()-self.time_play))/(self.length*1000)
		else:
			# Need length of track in ms
			l = pyg.mixer.music.get_pos()/(self.length*1000)
			
		# Normalise
		return normalise(l)
		
	
	def get_remaining(self):
		if self.is_sound:
			return self.length - (pyg.time.get_ticks()-self.time_play)/1000.0
		else:
			return self.length - pyg.mixer.music.get_pos()/1000.0
				
				
	def unload(self):
		self.active = False
		self.channel = -1

		
		
class Display:
	def __init__(self,player):
		pyg.init()
		# Create a pygame window
		self.scale = 2 # Only int works at the moment
		self.brightness = 1 # 1 is bright, higher numbers dimmer
		self.show_help = False
		self.set_colours()
		self.set_fonts()
		self.update_time = 50 #ms
		
		# Define sizes of things
		self.x_sidebar = 300 * self.scale
		self.y_header = 15 * self.scale #try to avoid multiples of y_cue (hides continuation bar at bottom)
		self.y_cue = 50 * self.scale
		self.gap = 5 * self.scale
		self.x_cue_number = 110 * self.scale # space for three digits (99 cues max before overlap)
		self.x_track_length = 110 * self.scale # space for one hour digit
		self.x_cue_icon = 30 *self.scale
		
		#screen = pyg.display.set_mode((0,0),pyg.RESIZABLE)
		# BODGE for my setup - can't work out how to maximise properly
		screen = pyg.display.set_mode((1900,1000),pyg.RESIZABLE)
		self.size = pyg.display.get_surface().get_size()
		self.set_caption(player.show_name)
		pyg.mouse.set_visible(False)
		pyg.time.Clock()
		self.surf = pyg.display.get_surface()
		self.surf.fill(self.colour['black'])
		
	
	def __del__(self):	
		# Quit pygame
		pyg.quit()
	
	
	def set_caption(self,caption = ''):
		if caption=='':
			pyg.display.set_caption('Cue Player')
		else:
			pyg.display.set_caption('Cue Player - '+caption)
	
	
	def set_fonts(self):
		self.font1 = pyg.font.Font(pyg.font.match_font('arial'),48*self.scale)
		self.font2 = pyg.font.Font(pyg.font.match_font('arial'),24*self.scale)
		self.font3 = pyg.font.Font(pyg.font.match_font('arial'),13*self.scale)
		# Fixed width font for numbers
		self.font1f = pyg.font.Font(pyg.font.match_font('monospace'),48*self.scale)
		#self.font1f.set_bold(True)
		self.font2f = pyg.font.Font(pyg.font.match_font('monospace'),24*self.scale)
		self.font2f.set_bold(True)
		self.font3f = pyg.font.Font(pyg.font.match_font('monospace'),13*self.scale)		
		self.font3f.set_bold(True)
		
		
	def set_colours(self):
		self.colour = {}
		f=1
		self.colour['black'] =		self.define_colour(0,	0,	0)
		self.colour['white'] =		self.define_colour(255,	255,255)
		self.colour['dark red'] =	self.define_colour(128,	0,	0)
		self.colour['red'] =		self.define_colour(255,	0,	0)
		self.colour['dark green'] = self.define_colour(0,	120,0)
		self.colour['green'] =		self.define_colour(0,	255,0)
		self.colour['grey']=		self.define_colour(100,	100,100)
		self.colour['blue']=		self.define_colour(90,	110,150)
		self.colour['yellow'] =		self.define_colour(200,	200,0)
		
		
	def define_colour(self,r,g,b):
		f = normalise(self.brightness)
		return pyg.Color(int(r*f),int(g*f),int(b*f),128)
		
		
	def update(self,player):
		# Current window size
		tx = int(self.size[0])
		ty = int(self.size[1])
		y = 0
		
		# Clear screen
		s = pyg.Surface(self.size)
		s.fill(self.colour['black'])
		self.surf.blit(s, (0,0))
		
		# Draw the sidebar
		self.surf.blit(self.sidebar(tx,ty,player),(0,0))
		
		# Work out how much of this will be respected by the cues (i.e. for small screens some overlap)
		this_x_sidebar = min(tx/3,self.x_sidebar)
				
		# Work out how much space is available for cues
		n_cues_visible =  math.floor((ty-self.y_header)/self.y_cue)
		if n_cues_visible<2:
			print "Window size is a bit too small - try a smaller scale factor"
			do_scroll = True
		elif n_cues_visible<player.n:
			do_scroll = True
		else:
			do_scroll = False
		
		# Work out which cues should be visible (i.e. what is offscreen when scrolling)
		do_draw = []
		total_visible = 0
		for i,c in enumerate(player.cues):
			if ((i>player.i-2 or c.active) and total_visible<n_cues_visible) or (player.n-i < n_cues_visible-total_visible):
			#if (((not do_scroll) or i>player.i-2 or c.active) and total_visible<n_cues_visible) or (player.n-i<n_cues_visible-total_visible):
				# If (less than 2 above selected and haven't yet run out of space ) or there's more space than cues left
				do_draw.append(True)
				total_visible+=1
			else:
				if c.active:
					print "Active cue not visible"
				do_draw.append(False)
				
		# Draw cues
		if len(player.cues)>0:
			y = self.y_header
			i = 0
			for i,c in enumerate(player.cues):
				if do_draw[i]:
					self.surf.blit(self.cuebar(c = c,w = tx-this_x_sidebar,hidden_above = not(i==0) and not(do_draw[i-1]),selected = i==player.i),(this_x_sidebar,y))
					y+=self.y_cue
			
			# If the last cue wasn't drawn
			if not(do_draw[i]):
				temp = pyg.Surface((tx-this_x_sidebar,self.gap))
				temp.fill(self.colour['white'])
				self.surf.blit(temp,(this_x_sidebar,y))
			
		pyg.display.update()
		
		
	def change_brightness(self,change):
		self.brightness =  normalise(self.brightness + change)
		self.set_colours()
		
		
	def toggle_fullscreen(self):
		pyg.display.toggle_fullscreen()


	def cuebar(self,c,w,hidden_above = False,selected = False):
		x = 0
		# Outer border
		s = pyg.Surface((w,self.y_cue))
		if selected:
			s.fill(self.colour['yellow'])
		else:
			s.fill(self.colour['black'])
		
		# Are there hidden cues above this one?
		if hidden_above:
			temp = pyg.Surface((w,self.gap))
			temp.fill(self.colour['white'])
			s.blit(temp,(0,0))
				
		# Text background
		temp = pyg.Surface((w-self.gap*2,self.y_cue-self.gap*2))
		
		if not(c.is_sound) and pyg.mixer.music.get_busy() and not c.active:
			this_blocked = True
		else:
			this_blocked = False
		if c.length==0 and not c.is_dummy:
			# Bad cue
			this_colour = self.colour['dark red']
		elif c.active:
			# Currently playing
			this_colour = self.colour['green']
		elif c.played:
			# Already played
			this_colour = self.colour['grey']
		else:
			# Waiting to be played
			this_colour = self.colour['blue']
		temp.fill(this_colour)
		s.blit(temp,(self.gap,self.gap))
		if c.is_playing():
			# Playing - bar to represent time taken
			temp = pyg.Surface((c.get_pos()*(w-self.gap*2),(self.y_cue-self.gap*2)))
			temp.fill(self.colour['dark green'])
		s.blit(temp,(self.gap,self.gap))

		# Text colour for the rest of the bar
		if c.played and not c.active:
			this_colour = self.colour['black']
		else:
			this_colour = self.colour['white']
							
		if c.is_dummy:
			# Dummy final cue
			text = self.font2.render(c.name,True,this_colour)
			x = (w-text.get_width())/2
			dy = text.get_height()
			s.blit(text,(x,(self.y_cue-dy)/2))
		else:
			# Cue number box
			text = self.font1f.render(str(c.cue_number),True,this_colour)
			dy = text.get_height()
			x += self.gap*2
			s.blit(text,(x,(self.y_cue-dy)/2))
			x+=self.x_cue_number
		
			# Cue length
			if c.active:
				if c.fade_start_time <> 0:
					text = self.font2f.render(format_time((c.fade_time - (pyg.time.get_ticks() - c.fade_start_time))/1000.0),True,self.colour['red'])
				else:
					# Time remaining
					text = self.font2f.render(format_time(c.get_remaining()),True,self.colour['black'])
			else:
				# Track length
				text = self.font2f.render(format_time(c.length),True,this_colour)
			dx = text.get_width()
			dy = text.get_height()
			x+=self.x_track_length # right aligned
			s.blit(text,(x-dx,(self.y_cue-dy)/2))
		
			# Icons for mp3/wav
			if c.is_sound:
				letter = "WAV"
				colour = self.colour['white']
			else:
				letter = "MP3"
				if this_blocked:
					colour = self.colour['green']
				else:
					colour = self.colour['black']
			text = self.font3f.render(letter,True,colour)
			dx = text.get_width()
			dy = text.get_height()
			x += self.gap*2
			s.blit(text,(x,(self.y_cue-dy)/2))
			x += self.x_cue_icon+self.gap
		
			# Cue name
			text = self.font2.render(c.name,True,this_colour)
			dy = text.get_height()
			s.blit(text,(x,(self.y_cue-dy)/2))
		
		return s
			

	def sidebar(self,tx,ty,player):
		y = 0
		s = pyg.Surface((self.x_sidebar,ty))
		s.fill(self.colour['black'])
		y+=self.gap*2
		
		# Show name
		#text = self.font2.render("Show",True,self.colour['blue'])
		#s.blit(text,(self.gap,y))
		#y+=text.get_height()
		#text = self.font2.render(player.show_name,True,self.colour['white'])
		#s.blit(text,(self.gap,y))
		#y+=text.get_height()
				
		# Clock
		#text = self.font2.render("Clock time",True,self.colour['blue'])
		#s.blit(text,(self.gap,y))
		#y+=text.get_height()
		text = self.font1f.render(str(datetime.datetime.now().strftime("%H:%M")),True,self.colour['white'])
		s.blit(text,(0,y))
		y+=text.get_height()
		
		# Total elapsed time
		if player.running:
			text = self.font2.render("Running time",True,self.colour['blue'])
			s.blit(text,(self.gap,y))
			dy = text.get_height()
			y+=dy
			text = self.font1f.render(str(datetime.datetime.now() - player.time_start).split('.')[0],True,self.colour['white'])
			s.blit(text,(self.gap,y))
			dy = text.get_height()
			y+=dy
				
		# Help
		#if self.show_help:
		#	s.blit(self.help_box(self.x_sidebar,ty/2.0),(0,ty/2.0))
		#else:
		#	text = self.font3.render("Press H for help",True,self.colour['white'])
		#	s.blit(text,(0,ty-text.get_height()))
		
		# Volume bar
		if player.have_volume:
			s.blit(self.volume_bar(self.x_sidebar*2/3.0,self.y_cue,player.get_system_volume()),(self.gap,ty-self.y_cue-self.gap))
	
		return s
	
	
	def help_box(self,w,h):
		s = pyg.Surface((w,h))
		#s.fill(self.colour['dark green'])
		# Keyboard shortcuts (working up from the bottom)
		y = h-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"Q","Quit"),(0,y))
		y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"R","Reload cuesheet"),(0,y))
		y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"F11","Fullscreen"),(0,y))
		y +=-self.y_cue
		#s.blit(self.button_box(self.y_cue,self.x_sidebar,"E","Edit mode"),(0,y))
		#y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"Escape","Stop all"),(0,y))
		y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"Space","Fade all"),(0,y))
		y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"Backspace","Fade last"),(0,y))
		y +=-self.y_cue
		s.blit(self.button_box(self.y_cue,self.x_sidebar,"Return","Play"),(0,y))
		
		text = self.font2.render("Controls",True,self.colour['blue'])
		y +=-text.get_height()
		s.blit(text,(0,y))	
		return s
		

	def button_box(self,h,w,text1,text2):
		gap = 5*self.scale
		s = pyg.Surface((w,h))
		#s.fill(self.colour['dark green'])
		# Scale grey box from cue height
		dx = 2*h
		temp = pyg.Surface((dx,h-gap*2))
		temp.fill(self.colour['grey'])
		s.blit(temp,(gap,gap))
		text = self.font3f.render(text1,True,self.colour['white'])
		dy = text.get_height()
		s.blit(text,((dx-text.get_width())/2,(h-dy)/2))
		text = self.font3.render(text2,True,self.colour['white'])
		s.blit(text,(dx+gap*3,(h-dy)/2))
		return s
		
		
	def volume_bar(self,w,h,vol):
		s = pyg.Surface((w,h))
		f = vol/100.0
		pyg.draw.polygon(s,self.colour['blue'],[[0,h],[w,0],[w,h]])
		pyg.draw.polygon(s,self.colour['white'],[[0,h],[f*w,(1-f)*h],[f*w,h]])
		text = self.font2.render(str(vol)+"%",True,self.colour['black'])
		s.blit(text,(w-text.get_width()-self.gap,h-text.get_height()-self.gap))
		return s
	

def event_handler(p,d,this_event):
	if this_event.type==pyg.QUIT:
		return 0
	elif this_event.type>=pyg.USEREVENT:
		# User events used to "unload"/deactivate cues at end of fade or play
		p.unload(this_event.type-pyg.USEREVENT)
	elif this_event.type==pyg.VIDEORESIZE:
		# Screen resize event
		d.size = this_event.dict['size']
		screen = pyg.display.set_mode(d.size,pyg.RESIZABLE)
		d.update(p)
	elif this_event.type==pyg.KEYUP:
		pass
	elif this_event.type==pyg.KEYDOWN:
		if this_event.key==pyg.K_q:
			return 0
		elif this_event.key==pyg.K_r:
			p.reset()
		elif this_event.key==pyg.K_h:
			# Toggle key legend
			d.show_help = not d.show_help
		elif this_event.key==pyg.K_F11:
			d.toggle_fullscreen()
		elif this_event.key==pyg.K_RETURN:
			p.play_selected()
		elif this_event.key==pyg.K_BACKSPACE:
			p.fadeout_last()
		elif this_event.key==pyg.K_SPACE:
			p.fadeout_all()
		#elif this_event.key==pyg.K_RIGHT:
		#elif this_event.key==pyg.K_LEFT:
		elif this_event.key==pyg.K_DOWN:
			p.down()
		elif this_event.key==pyg.K_UP:
			p.up()
			# TODO - hold down behaviour
		elif this_event.key==pyg.K_ESCAPE:
			p.stop_all()
		elif this_event.key==pyg.K_HOME:
			p.i = 0  # Jump to start
		elif this_event.key==pyg.K_END:
			p.i = p.n # Jump to end
		elif this_event.key==pyg.K_LEFTBRACKET:
			d.change_brightness(-0.1)
		elif this_event.key==pyg.K_RIGHTBRACKET:
			d.change_brightness(0.1)
		elif this_event.key==pyg.K_EQUALS:
			# System volume up
			p.set_system_volume(5)
		elif this_event.key==pyg.K_MINUS:
			# System volume down
			p.set_system_volume(-5)
		#elif this_event.key==pyg.K_DELETE:
		#elif this_event.key>=pyg.K_F1 and this_event.key<=pyg.K_F12:
		#elif this_event.key>=pyg.K_1 and this_event.key<=pyg.K_9:
		#elif this_event.key==pyg.K_0:
		# e = edit
		
		# Display update
		d.update(p)
		
	return 1

def format_time(time):
	# Convert time in s to something useful
	if time<1:
		text = "0"
	elif time<60:
		# Seconds only
		text = "%1.0f" % time
	elif time<3600:
		# Minutes
		text = "%1.0f:%02.0f" % (math.floor(time/60),math.floor(time%60))
	else:
		# Hours
		text = "%1.0f:%02.0f:%02.0f" % (math.floor(time/3600),math.floor((time/60)%60),math.floor(time%60))
	return text
		
		
def normalise(x,max_x = 1):
	return min(max(float(x),0),max_x)
	
		
def create_cue_sheet(folder):
	# Auto generate a list of files in the current folder and export as a cue sheet
	output_text = "# Cue number, cue name, filename\n"
	
	i = 10
	for filename in os.listdir(folder):
		if filename[-3:].lower()=="mp3" or filename[-3:].lower()=="ogg" or filename[-3:].lower()=="wav":
			output_text += str(i)+","+filename[:-4]+","+filename + ",500\n"
			i+=10
	
	output_file	 = "test.cus"
	
	with open(output_file,'wt') as fid:
		fid.write(output_text+'\n')
	
	return output_file



def main(cue_sheet = ""):
	if not os.path.isfile(cue_sheet):
		if os.path.isfile("test.cus"):
			print "Cue sheet not found, using default 'test.cus' found in current folder"
			cue_sheet = "test.cus"
		else:
			print "Cue sheet not found, creating a new one from sound files in the current folder"
			cue_sheet = create_cue_sheet("./")
	
	
	# Create an instance of the player class
	p = Player(cue_sheet)
		
	# Create an instance of the display class
	d = Display(p)
	d.update(p)

	# Main loop - basically just waiting for key events
	last_t = 0
	running = True
	while running:
		for this_event in pyg.event.get():
			last_event = pyg.time.get_ticks()
			if not(event_handler(p,d,this_event)):
				running = False
				return 1
				
		# Do regular updates (frequency alterable in config)
		t = pyg.time.get_ticks()
		if t-last_t>d.update_time:
			last_t = t
			d.update(p)


if __name__ == '__main__':
	if len(sys.argv)>1:
		main(sys.argv[1])
	else:
		main()
