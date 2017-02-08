from __future__ import print_function

import logging as log
import os
import struct
import subprocess
import time

from bluepy import btle
#import btle
import myo_dicts

# Author:
#    Max Leefer
# Contributor:
#   Siarhei Yorsh (MyrikLD)
# Source:
#    https://github.com/mamo91/Dongleless-myo
# Free to modify and use as you wish, so long as my name remains in this file.
# Special thanks to the support at Thalmic labs for their help, and to IanHarvey for bluepy


# Notes
# If the Myo is unsynced while the program is running, you will need to plug it in and let it fall asleep before poses will work again.
# Mixes up fist and wave in when worn on left arm with led toward elbow


PATH = os.getcwd()

busylog = False  # decides whether emg/imu notifications will generate log messages.
log.basicConfig(filename=PATH + "/dongleless.log", filemode='w', level=log.INFO,
				# change log.CRITICAL to log.DEBUG to get log messages
				format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S')


class Connection(btle.Peripheral):
	def __init__(self, mac):
		btle.Peripheral.__init__(self, mac)

		# self.writeCharacteristic(0x19, struct.pack('<bbbbb', 0,0,0,3,1) ,True ) # Tell the myo we want neither IMU nor classifier data
		# self.writeCharacteristic(0x24, struct.pack('<bb', 0x00, 0x00),True) # Unsubscribe from classifier indications

		# time.sleep(0.5)

		self.writeCharacteristic(0x24, struct.pack('<bb', 0x02, 0x00), True)  # Subscribe to classifier indications
		self.writeCharacteristic(0x1d, struct.pack('<bb', 0x01, 0x00), True)  # Subscribe to imu notifications
		self.writeCharacteristic(0x28, struct.pack('<bb', 0x01, 0x00), True)  # Subscribe to emg notifications
		self.writeCharacteristic(0x19, struct.pack('<bbbbb', 1, 1, 1, 3, 1), True)  # Tell the myo we want all the data

	def vibrate(self, length):
		self.writeCharacteristic(0x19, struct.pack('<bbb', 0x03, 0x01, length), True)


class MyoDelegate(btle.DefaultDelegate):
	def __init__(self, bindings, myo):
		self.bindings = bindings
		self.myo = myo

	def handleNotification(self, cHandle, data):
		if cHandle == 0x23:
			log.debug("got pose notification")
			ev_type = None
			data = struct.unpack('>6b',
								 data)  # sometimes gets the poses mixed up, if this happens, try wearing it in a different orientation.
			if data[0] == 3:  # CLassifier
				ev_type = myo_dicts.pose[data[1]]
				# print(ev_type)
				if data[1] != 0:
					self.myo.writeCharacteristic(0x19, struct.pack('<bbb', 0x03, 0x01, 0x01), True)

			else:
				if data[0] == 1:  # sync
					log.info("Arm synced")
					ev_type = "arm_synced"
					# rewrite handles
					self.myo.writeCharacteristic(0x19, struct.pack('<bbbbb', 1, 1, 0, 3, 1),
												 True)  # Tell the myo we want IMU and classifier data
					self.myo.writeCharacteristic(0x24, struct.pack('<bb', 0x02, 0x00),
												 True)  # Subscribe to classifier indications
					self.myo.writeCharacteristic(0x28, struct.pack('<bb', 0x00, 0x00),
												 True)  # Subscribe to classifier indications
					self.myo.writeCharacteristic(0x1d, struct.pack('<bb', 0x01, 0x00),
												 True)  # Subscribe to classifier indications
					# self.myo.writeCharacteristic(0x1d, struct.pack('<bb', 0x01, 0x00),True) # Subscribe to IMU notifications

					if data[1] == 2:  # left arm
						self.arm = "left"
					elif data[1] == 1:  # right arm
						self.arm = "right"
					else:
						self.arm = "unknown"
					if 'arm_synced' in self.bindings:
						self.bindings['arm_synced'](self.myo, myo_dicts.x_direction[data[2]], myo_dicts.arm[data[1]])
					return

			if ev_type in self.bindings:
				self.bindings[ev_type](self.myo)

		elif cHandle == 0x1c:  # IMU
			data = struct.unpack('<10h', data)
			quat = data[:4]
			accel = data[4:7]
			gyro = data[7:]
			if busylog:
				log.debug("got imu notification")
			ev_type = "imu_data"
			if "imu_data" in self.bindings:
				self.bindings["imu_data"](self.myo, quat, accel, gyro)

		elif cHandle == 0x27:  # EMG
			data = struct.unpack('<8HB', data)  # an extra byte for some reason
			if busylog:
				log.debug("got emg notification")
			ev_type = "emg_data"
			if "emg_data" in self.bindings:
				self.bindings["emg_data"](self.myo, data[:8])


# def quat_to_euler(w,x,y,z):
# 	# Calculate Euler angles (roll, pitch, and yaw) from the unit quaternion.
# 	w,x,y,z = [a/16384 for a in [w,x,y,z]]
# 	roll = math.atan2(2.0 * (w * x + y * z),
# 					   1.0 - 2.0 * (x * x + y * y))
# 	pitch = math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))
# 	yaw = math.atan2(2.0 * (w * z + x * y),
# 					1.0 - 2.0 * (y * y + z * z))
# 	# // Convert the floating point angles in radians to a scale from 0 to 18.


# 	result = ((roll + (math.pi))/(math.pi * 2.0) * 18, # roll
# 			(pitch + (math.pi/2.0)/math.pi * 18),      # pitch
# 			(yaw + (math.pi)/(math.pi * 2.0) * 18) )   # yaw


# 	# print ("in: {} out: {}".format((w,x,y,z), result)),
# 	return result
# 	# print(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))


def print_wrapper(*args):
	print(args)


# take a list of the events.
events = ("rest", "fist", "wave_in", "wave_out", "wave_left", "wave_right",
		  "fingers_spread", "double_tap", "unknown", "arm_synced", "arm_unsynced",
		  "orientation_data", "gyroscope_data", "accelerometer_data", "imu_data", "emg_data")


# Bluepy is more suited to getting default values like heartrate and such, it's not great at fetching by uuid.

def find_mac(blacklist=list(), password=None, timeout=3, passive=False, root=True):
	c = str()

	if root:
		sudo = 'sudo '
		if password is not None:
			c += 'echo ' + str(password) + ' | '
			sudo += '-S '
	else:
		sudo = ''

	if timeout is not None:
		c += sudo + 'timeout -s SIGINT -k 0 ' + str(timeout) + ' '

	c += sudo + 'hcitool lescan' + (' --passive' if passive else '')

	if password is not None and root:
		process = subprocess.Popen(c, stdout=subprocess.PIPE,
								   stderr=subprocess.PIPE,
								   stdin=subprocess.PIPE,
								   shell=True)
	else:
		process = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
	output, unused_err = process.communicate()

	retcode = process.poll()
	if retcode != 124:
		raise subprocess.CalledProcessError(retcode, c, output=output)

	lines = output.strip().split('\n')
	# timing is a bit weird.

	lines = lines[1:]
	ret = list()
	for line in lines:
		p = line.find(' ')
		sp = line[:p], line[p:]
		if sp[0] not in blacklist:
			ret.append(sp)
	return ret


def run(modes):
	# Takes one argument, a dictionary of names of events to functions to be called when they occur.
	# Main loop --------
	while True:
		blacklist = []
		try:
			log.info("Initializing bluepy connection.")
			p = None
			while not p:
				x = find_mac(blacklist=blacklist)
				#print(x)
				for dev in x:
					mac = dev[0]
					try:
						log.info('Try to connect '+str(mac))
						p = Connection(mac)  # Takes a long time if it's not a myo
						if p:
							log.info("Found Myo at MAC: %s" % mac)
							break
						else:
							blacklist.append(mac)
					except btle.BTLEException:
						log.info("Found something that is not a Myo, adding to blacklist and trying again.")
						log.debug("could not write to %s, ignored" % mac)
						del p
						p = None
						blacklist.append(mac)
						time.sleep(0.5)

			p.setDelegate(MyoDelegate(modes, p))

			# Maybe try starting a new thread instead? *Might* work with multiple myos then.

			log.info("Initialization complete.")
			while True:
				# break
				try:
					p.waitForNotifications(3)
				except btle.BTLEException:
					log.info("Disconnected")
					break
		except KeyboardInterrupt:
			log.warning("KeyboardInterrupt")
			break
		# except:
		#     log.critical("Unexpected error:", sys.exc_info()[0])
	log.warning("Program stopped")
