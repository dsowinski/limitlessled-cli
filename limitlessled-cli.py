#!/usr/bin/env python3
# Script to control LimitlessLED DualWhite, RGB+W and RGBWW/CW bulbs through v6 WiFi Bridge.
#
# Benny Wydooghe's work for Domoticz has been a huge influence while making this script, 
# which is tailored to be a CLI tool for integration with HA-bridge and Amazon Echo (Alexa).
#
# Requires Python 3.
#
# Used http://www.limitlessled.com/dev/ as reference and for examples, to extract
# UDP codes valid for API v6. Also, since the official API description is not complete, 
# I had to hunt for the info and found it here at:
#    https://github.com/mwittig/node-milight-promise/blob/master/src/commandsV6.js
# which enabled me to implement DualWhite bulbs support, thanks!


import socket
import sys
import time
import getopt
import binascii
import ipaddress
import select

__version__ = str(0.7)
__changed__ = str(20170113)
__author__ = "Dariusz Sowinski"
__email__ = "d@sowin.ski"

logfile = "limitlessled-cli.log" # Filename where some debug messages are written to
help = """LimitlessLED-CLI v""" + str(__version__) + """ (""" + str(__changed__) + """)
Copyright (c) """ + __changed__[:4] + """ by """ + __author__ + """ <""" + __email__ + """>

Usage: """ + sys.argv[0] + """ -c <command> -t <device_type> -b <bridge_ip> -z <zone> -p <extra param>")

Options:
	-c,--command		provide a command to be sent to bridge [mandatory]:
				    - Universal: 		ON, OFF, NIGHT
				    - DualWhite: 		BRIGHTUP, BRIGHTDOWN, BRIGHTMAX,
								WARMER, COOLER
				    - RGBW & RGBW/WW/CW:	BRIGHT, KELVIN, MODE, MODEFASTER,
								MODESLOWER, WHITE, COLOR
				    - RGBWWCW:			SATURATION
				    - iBox Bridge:		WHITE, BRIGHT, MODE, COLOR
				NOTE: There are predefined color sets than can be called with
				      the following commands:
				      LAVENDER, BLUE, AQUA, GREEN, LIME, YELLOW, ORANGE
	-t,--type		type of bulb the command is being sent to [mandatory]:
				    - WHITE     (DualWhite) - white only bulbs
				    - RGBW      (RGBWW or RGBCW) - previous generation
				    - RGBWW     (RGBW/WW/CW) - latest generation
        -b,--bridge_ip		provide an IP address of the bridge [mandatory]
	-f,--force		force repeated attempts when device type is WHITE
				INFO: This is a hack to allow HA-bridge to first send a BRIGHTMAX
				      command and then send a correct number of BRIGHTDOWN messages
				      to set the brightness of the bulb based on the percentage
				      value of the optional parameter. So far this is my best
				      attempt at making it possible. If you have a better idea
				      for such functionality, please let me know!
	-h,--help		print this help screen
	-o,--override		override the command (for debug purposes, use discouraged)
        -p,--parameter		optional parameter depending on selected command and type:
				    - Percentage (0-100) for brightness, examples:
				      0%   = 2700K (Warm White)
				      25%  = 3650K
				      50%  = 4600K
				      75%  = 5550K
				      100% = 6500K (Cool White)
				    - Percentage (0-100) for saturation [RGBW/WW/CW only]
				    - Range 1-9 for "disco" modes
				    - Range 0-255 for color
	-v,--verbose		verbose output on screen
	-z,--zone		provide zone/group of lamps in range  1-4 [defaults to 0 (all)]

Examples:
	1. Turn on RGBWW zone 2:
	   """ + sys.argv[0] + """ -c ON -t RGBWW -b 192.168.1.120 -z 2
	2. Set RGBWW zone 2 to white:
	   """ + sys.argv[0] + """ -c WHITE -t RGBWW -b 192.168.1.120 -z 2
	3. Set RGBWW zone 2 to disco mode 6:
           """ + sys.argv[0] + """ -c MODE -t RGBWW -b 192.168.1.120 -z 2 -p 6
	4. Set all WHITE zones to max brightness:
           """ + sys.argv[0] + """ -c BRIGHTMAX -t WHITE -b 192.168.1.120
	5. Increase brightness for all WHITE zones by 20%:
           """ + sys.argv[0] + """ -c BRIGHTUP -t WHITE -b 192.168.1.120 -p 20
	6. Decrease brightness for all WHITE zones by 20%:
           """ + sys.argv[0] + """ -c BRIGHTDOWN -t WHITE -b 192.168.1.120 -p 20
	7. Turn night mode on iBox Bridge LED lamp:
           """ + sys.argv[0] + """ -c NIGHT -t IBOX -b 192.168.1.120 -v

Debug usage:
	Set iBox Bridge LED lamp to color red:
	""" + sys.argv[0] + """ -t IBOX -b 192.168.1.120 -v -o -p "31 00 00 00 01 FF FF FF FF 00 00"
"""


def usage():
	print(help)


def log(pref, message):
	debug_message = time.ctime() + " [" + pref + "] " + message
	if verbose:
		print(debug_message)
	file = open(logfile, "a")
	file.write(debug_message + "\n")
	file.close()


def get_command(usercommand, device_type, zone):
	command_bridgeled = {
        "ON"            : "31 00 00 XX 03 03 00 00 00 00 00",
        "OFF"           : "31 00 00 XX 03 04 00 00 00 00 00",
        "WHITE"         : "31 00 00 XX 03 05 00 00 00 00 00",
        "NIGHT"         : "31 00 00 XX 03 06 00 00 00 00 00",
	"BRIGHT"        : "31 00 00 XX 02 00 00 00 00 00 00",
	"MODE"		: "31 00 00 XX 04 00 00 00 00 00 00",
	"COLOR"		: "31 00 00 XX 01 00 00 00 00 00 00",
	"RED"		: "31 00 00 XX 01 FF FF FF FF 00 00",
	"LAVENDER"      : "31 00 00 XX 01 D9 D9 D9 D9 00 00",
	"BLUE"          : "31 00 00 XX 01 BA BA BA BA 00 00",
	"AQUA"          : "31 00 00 XX 01 85 85 85 85 00 00",
	"GREEN"         : "31 00 00 XX 01 7A 7A 7A 7A 00 00",
	"LIME"          : "31 00 00 XX 01 54 54 54 54 00 00",
	"YELLOW"        : "31 00 00 XX 01 3B 3B 3B 3B 00 00",
	"ORANGE"        : "31 00 00 XX 01 1E 1E 1E 1E 00 00",
	}

	command_dualwhite = {
        "ON"            : "31 00 00 XX 01 07 00 00 00 00 00",
        "OFF"           : "31 00 00 XX 01 08 00 00 00 00 00",
        "BRIGHTUP"      : "31 00 00 XX 01 01 00 00 00 00 00",
        "BRIGHTDOWN"    : "31 00 00 XX 01 02 00 00 00 00 00",
        "BRIGHTMAX"     : "31 00 00 XX 81 07 00 00 00 00 00",
        "NIGHT"         : "31 00 00 XX 01 06 00 00 00 00 00",
        "WARMER"        : "31 00 00 XX 01 03 00 00 00 00 00",
        "COOLER"        : "31 00 00 XX 01 04 00 00 00 00 00",
	}

	command_colour = {
        "ON"            : "31 00 00 XX 04 01 00 00 00 00 00",
        "OFF"           : "31 00 00 XX 04 02 00 00 00 00 00",
	"NIGHT"		: "31 00 00 XX 04 05 00 00 00 00 00",
        "BRIGHT"        : "31 00 00 XX 03 00 00 00 00 00 00",
	"WHITE"		: "31 00 00 XX 05 64 00 00 00 00 00",
	"KELVIN"	: "31 00 00 XX 05 00 00 00 00 00 00",
	"SATURATION"	: "31 00 00 XX 02 00 00 00 00 00 00",
        "MODE"          : "31 00 00 XX 04 00 00 00 00 00 00",
        "MODEFASTER"    : "31 00 00 XX 04 03 00 00 00 00 00",
        "MODESLOWER"    : "31 00 00 XX 04 04 00 00 00 00 00",
        "RED"           : "31 00 00 XX 01 00 00 00 FF 00 00",
	"LAVENDER"	: "31 00 00 XX 01 00 00 00 D9 00 00",
	"BLUE"          : "31 00 00 XX 01 00 00 00 BA 00 00",
	"AQUA"          : "31 00 00 XX 01 00 00 00 85 00 00",
        "GREEN"         : "31 00 00 XX 01 00 00 00 7A 00 00",
        "LIME"          : "31 00 00 XX 01 00 00 00 54 00 00",
	"YELLOW"        : "31 00 00 XX 01 00 00 00 3B 00 00",
	"ORANGE"        : "31 00 00 XX 01 00 00 00 1E 00 00",
	}

	if override:
		command = str(usercommand)
	elif device_type == "IBOX":
		device = "00"
		try:
			command = command_bridgeled.get(usercommand).replace("XX", device)
		except:
			log("ERROR", "Command not found!")
			sys.exit(1)
	elif device_type == "WHITE":
		device = "01"
		try:
			command = command_dualwhite.get(usercommand).replace("XX", device)
		except:
			log("ERROR", "Command not found!")
			sys.exit(1)
	elif device_type == "RGBW":
		device = "07"
		try:
			command = command_colour.get(usercommand).replace("XX", device)
			command = command[:12] + "03" + command[14:]
		except:
			log("ERROR", "Command not found!")
			sys.exit(1)
	elif device_type == "RGBWW":
		device = "08"
		try:
			command = command_colour.get(usercommand).replace("XX", device)
		except:
			log("ERROR", "Command not found!")
			sys.exit(1)
	else:
		log("ERROR", "Unknown device type!")
		sys.exit(1)

	if usercommand == "BRIGHT" or usercommand == "KELVIN":
		if device_type == "RGBW":
			command = command[:12] + "02" + command[14:]

		try:
			percent = int(param)
			percent = hex(percent)[2:].zfill(2).upper()
			command = command[:15] + percent + command[17:]
		except:
			log("ERROR", "No extra parameter provided, aborting!")
			sys.exit(1)

	if usercommand == "MODE":
		try:
			mode = int(param)
			if mode >= 1 and mode <= 9:
				mode = hex(mode)[2:].zfill(2).upper()
				command = command[:15] + mode + command[17:]
			else:
				log("ERROR", "Parameter out of range (1-9).")
				sys.exit(1)
		except:
			log("ERROR", "No extra parameter provided, aborting!")
			sys.exit(1)

	if usercommand == "SATURATION":
		try:
			saturation = int(param)
			if saturation >= 0 and saturation <= 100:
				saturation = hex(saturation)[2:].zfill(2).upper()
				command = command[:15] + saturation + command[17:]
			else:
				log("ERROR", "Parameter out of range (0-100).")
				sys.exit(1)
		except:
			log("ERROR", "No extra parameter provided, aborting!")
			sys.exit(1)

	if usercommand == "COLOR":
		try:
			color = int(param)
			if color >= 0 and color <= 255:
				color = hex(color)[2:].zfill(2).upper()
				color_msg = color + " "
				for count in range(0, 3):
					color_msg += str(color) + " "
				command = command[:15] + color_msg + command[27:]
			else:
				log("ERROR", "Parameter out of range (0-255).")
				sys.exit(1)
		except:
			log("ERROR", "No extra parameter provided, aborting!")
			sys.exit(1)

	if zone >= 0 and zone <= 4:
		zone = "%02d" % zone
	else:
		log("ERROR", "Zone out of range (1-4).")
		sys.exit(1)

	command = command[:27] + zone + command[29:]
	return command


def get_message(ibox_id1, ibox_id2, usercommand):
	return "80 00 00 00 11" + " " + ibox_id1 + " " + ibox_id2 + " " + "00 00 00" + " " + usercommand


def main():
	count = 0
	zone = 0
	global verbose
	verbose = False
	global param
	param = None
	global override
	override = False
	force = False
	udp_port = 5987 # UDP port on which we will communicate with the iBox
	udp_port_receive = 55054 # UDP port on which we will listen for responses
	udp_times_to_send_command = 5 # Number of times you want to send the UDP commands to the iBox
	udp_socket_timeout = 5

	try:
		opts, args = getopt.getopt(sys.argv[1:], "c:t:b:z:p:hvof", ["command=", "type=", "bridge_ip=", "zone=", "parameter=", "help", "verbose", "override", "force"])
	except getopt.GetoptError as e:
		log("ERROR", str(e))
		usage()
		sys.exit(2)

	for o, a in opts:
		if o == "-v":
			verbose = True
		elif o in ("-h", "--help"):
			usage()
			sys.exit()
		elif o in ("-c", "--command"):
			usercommand = a
		elif o in ("-t", "--type"):
			device_type = a
		elif o in ("-b", "--bridge_ip"):
			bridge_ip = a
		elif o in ("-z", "--zone"):
			zone = int(a)
		elif o in ("-p", "--parameter"):
			param = a.replace("%", "")
		elif o in ("-o", "--override"):
			override = True
			usercommand = "OVERRIDE"
		elif o in ("-f", "--force"):
			force = True
		else:
			assert False, "Unhandled option"

	if len(sys.argv) == 1:
		usage()
		sys.exit()

	try:
		usercommand
		device_type
		bridge_ip
	except NameError:
		log("ERROR", "Required options not provided!")
		sys.exit(1)

	if usercommand == "BRIGHTUP" or usercommand == "COOLER":
		try:
			percent = int(param)
			conv = percent / 10
			repeats = int(conv)
		except:
			repeats = 1
	elif usercommand == "BRIGHTDOWN" or usercommand == "WARMER":
		try:
			percent = int(param)
			conv = ((percent / 100) -1) * -11
			repeats = int(conv)
		except:
			repeats = 1
	else:
		repeats = 1

	if verbose:
		log("DEBUG", "ZONE: " + str(zone) + ", PARAMETER: " + str(param) + ", REPEATS: " + str(repeats))


	# LimitlessLED iBox Bridge initial message to start a session.
	message = "20 00 00 00 16 02 62 3A D5 ED A3 01 AE 08 2D 46 61 41 A7 F6 DC AF D3 E6 00 00 1E"

	if override:
		command = get_command(param, device_type, zone)
	else:
		command = get_command(usercommand, device_type, zone)
	checksum = ('%x' % sum(int(x, 16) for x in command.split())).upper()
	checksum = checksum[-2:]
	command += " " + checksum

	# STEP 1: Send initial UDP message to iBox Bridge to start session and receive response.
	try:
		ipaddress.ip_address(bridge_ip)
	except Exception as e:
		log("ERROR", str(e))
		sys.exit(1)

	udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	udp_socket.settimeout(10)
	udp_socket.setblocking(0)
	udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	udp_socket.bind(('', udp_port_receive))
	udp_socket.sendto(bytearray.fromhex(message), (bridge_ip, udp_port))

	udp_sock_status = select.select([udp_socket], [], [], udp_socket_timeout)

	if udp_sock_status[0]:
		try:
			data, addr = udp_socket.recvfrom(1024)
		except Exception as e:
			log("ERROR", str(e))
			sys.exit(1)

		# STEP 2: Extract iBox Bridge ID1 and ID2 from response.
		response = str(binascii.hexlify(data), 'ascii')
		ibox_id1 = response[38:40].upper()
		ibox_id2 = response[40:42].upper()
		log("INFO", "Received message: " + response + " (initialisation)")
		log("INFO", "Received message: " + ibox_id1 + " (ibox identifier 1)")
		log("INFO", "Received message: " + ibox_id2 + " (ibox identifier 2)")

		# STEP 3: Find correct UDP code for specified command.
		message_command = get_message(ibox_id1, ibox_id2, command)
		log_line = "Sending message: " + message_command
		if device_type == "WHITE":
			log_line += " (repeated " + str(repeats) + " times)"
		log("INFO", log_line)

		while count < repeats:
			count += 1
			if device_type != "WHITE" or force:
				for attempt in range(0, udp_times_to_send_command):
					attempt += 1
					udp_socket.sendto(bytearray.fromhex(message_command), (bridge_ip, udp_port))
					log("INFO", "Message sent! (attempt #" + str(attempt) + ")")
					time.sleep(0.2)
			# The below is a workaround for commands sent to DualWhite bulbs when specifying
			# a repeated command based on the parameter percentage value. If the packet is lost,
			# execution of the command will fail. This is a hack to allow HA-bridge to first
			# send a BRIGHTMAX command and then send a correct number of BRIGHTDOWN messages
			# to set the brightness of the bulb based on the parameter percentage value. 
			# If you have a better idea for such functionality, please let me know!
			else:
				log("WARN", "Device type is DualWhite (WHITE), skipping multiple attempts - see README for details.")
				udp_socket.sendto(bytearray.fromhex(message_command), (bridge_ip, udp_port))
				log("INFO", "Message sent!")
		udp_socket.close()
		log("INFO", "All done, quitting.")
		sys.exit(0)

if __name__ == "__main__":
	main()
