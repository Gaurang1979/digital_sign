#!/bin/bash
#
#HYP2003 device mode change script
#

#test current user
TEMP_PATH=$0
if test $(id -ur) != 0; then
        echo "You should login as root user!"
        echo
        exit -1
fi

#Revise usb hotplug script for regular user can use HYP2003 USB Token
if [ -f /etc/hotplug/usb.agent ]; then
	declare -i start=0
        declare -i end=0
        declare -i headline=0
        declare -i endline=0
	start=`cat /etc/hotplug/usb.agent -n | grep "Change mode for HYP2003 USB Token" | head -1 | cut -f1`
	if [ $start != 0 ]; then
		cp /etc/hotplug/usb.agent /etc/hotplug/usb.agent.bak
		end=`cat /etc/hotplug/usb.agent| wc -l`
		headline=$start-2
		endline=$end-$start-12
		head -n $headline /etc/hotplug/usb.agent.bak > /etc/hotplug/usb.agent
		tail -n $endline /etc/hotplug/usb.agent.bak >> /etc/hotplug/usb.agent
		rm /etc/hotplug/usb.agent.bak
	fi
else
	if [ -d /etc/udev/rules.d/ ]; then
		count=`find /etc/udev/rules.d/HYP2003_token*.rules|wc -l`
		if [ $count -ge 1 ]; then
			rm -f /etc/udev/rules.d/HYP2003_token*.rules
#			service udev reload &>/dev/null
			if service udev reload &>/dev/null;
			then
				echo "Service udev reload!"
			else
				echo "Please restart your computer in order for this change of udev rules to take effect"                       
			fi
		fi
	else
		echo Please install hotplug or udev tools!!!
	fi
fi

echo run finished!


