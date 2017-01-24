# limitlessled-cli
Python CLI tool to control LimitlessLED RGBW/WW/CW, RGBW and DualWhite bulbs with iBox Bridge (API v6)

[Benny Wydooghe's work for Domoticz](https://github.com/bwydoogh/domoticz-scripts) has been a huge influence while making this script (thanks!), which is tailored to be a CLI tool for integration with HA-bridge and Amazon Echo (Alexa).

Used http://www.limitlessled.com/dev/ as reference and for examples, to extract UDP codes valid for API v6. Also, since the official API description is not complete, I had to hunt for the info and found it here at: https://github.com/mwittig/node-milight-promise/blob/master/src/commandsV6.js which enabled me to implement DualWhite bulbs support, thanks!

Requires Python 3.


# Usage

## Command syntax
```
./limitlessled-cli.py -c <command> -t <device_type> -b <bridge_ip> -z <zone> -p <extra param> [-fhov]
```

## Available options

- Command (```-c,--command```) - provide a command to be sent to bridge [mandatory]:
	- Universal: 
	**ON**, **OFF**, **NIGHT**
	- DualWhite: 
	**BRIGHTUP**, **BRIGHTDOWN**, **BRIGHTMAX**, **WARMER**, **COOLER**
	- RGBW & RGBW/WW/CW: 
	**BRIGHT**, **KELVIN**, **MODE**, **MODEFASTER**, **MODESLOWER**, **WHITE**, **COLOR**
	- RGBWWCW: 
	**SATURATION**
	- iBox Bridge:	
	**WHITE**, **BRIGHT**, **MODE**, **COLOR**

***NOTE**: There are predefined color sets than can be called with the following commands:
LAVENDER, BLUE, AQUA, GREEN, LIME, YELLOW, ORANGE*

- Device type (```-t,--type```) - type of bulb the command is being sent to [mandatory]:
	- **WHITE**     (DualWhite) - white only bulbs
	- **RGBW**      (RGBWW or RGBCW) - previous generation
	- **RGBWW**     (RGBW/WW/CW) - latest generation
- Bridge address (```-b,--bridge_ip```) - provide an IP address of the bridge [mandatory]
- Force repeated attempts (```-f,--force```) - force repeated attempts when device type is WHITE
***INFO**: This is a hack to allow HA-bridge to first send a BRIGHTMAX command and then send a correct number of BRIGHTDOWN messages to set the brightness of the bulb based on the percentage value of the optional parameter. So far this is my best attempt at making it possible. If you have a better idea for such functionality, please let me know!*
- Help screen (```-h,--help```) - print this help screen
- Override command (```-o,--override```) - override the command (for debug purposes, use discouraged)
- Optional parameter (```-p,--parameter```) - optional parameter depending on selected command and type:
	- Percentage (0-100) for brightness, examples:
				      0%   = 2700K (Warm White)
				      25%  = 3650K
				      50%  = 4600K
				      75%  = 5550K
				      100% = 6500K (Cool White)
	- Percentage (0-100) for saturation [RGBW/WW/CW only]
	- Range 1-9 for "disco" modes
	- Range 0-255 for color
- Verbode output (```-v,--verbose```) - verbose outputto stdout
- Device zone/group (```-z,--zone```) - provide zone/group of lamps in range  1-4 [defaults to 0 (all)]



### Examples:
1. Turn on RGBWW zone 2:

        ./limitlessled-cli.py -c ON -t RGBWW -b 192.168.1.120 -z 2

2. Set RGBWW zone 2 to white:

        ./limitlessled-cli.py -c WHITE -t RGBWW -b 192.168.1.120 -z 2

3. Set RGBWW zone 2 to disco mode 6:

        ./limitlessled-cli.py -c MODE -t RGBWW -b 192.168.1.120 -z 2 -p 6

4. Set all WHITE zones to max brightness:

        ./limitlessled-cli.py -c BRIGHTMAX -t WHITE -b 192.168.1.120

5. Increase brightness for all WHITE zones by 20%:

        ./limitlessled-cli.py -c BRIGHTUP -t WHITE -b 192.168.1.120 -p 20

6. Decrease brightness for all WHITE zones by 20%:

        ./limitlessled-cli.py -c BRIGHTDOWN -t WHITE -b 192.168.1.120 -p 20

7. Turn night mode on iBox Bridge LED lamp:

        ./limitlessled-cli.py -c NIGHT -t IBOX -b 192.168.1.120 -v


### Debug commands:
Set iBox Bridge LED lamp to color red:
           
    ./limitlessled-cli.py -t IBOX -b 192.168.1.120 -v -o -p "31 00 00 00 01 FF FF FF FF 00 00"
