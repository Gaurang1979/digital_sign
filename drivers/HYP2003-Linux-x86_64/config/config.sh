#!/bin/bash
#
#HYP2003 device mode change script
#

#test current user
TEMP_PATH=$0
if test $(id -ur) != 0; then
        echo
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
#start=`cat /etc/hotplug/usb.agent -n | grep "PRO=\`echo $PRODUCT | cut -d/ -f1\`" | head -1 | cut -f1`
	start=`cat /etc/hotplug/usb.agent -n | grep "Change mode for HYP2003 USB Token" | head -1 | cut -f1`
        if [ $start = 0 ]; then
		cp /etc/hotplug/usb.agent /etc/hotplug/usb.agent.bak
                grep "hotplug.functions" /etc/hotplug/usb.agent > /dev/null
                if [ $? = 0 ]; then
                	start=`cat /etc/hotplug/usb.agent -n | grep "hotplug.functions" | head -1 | cut -f1`
                	end=`cat /etc/hotplug/usb.agent | wc -l`
                	headline=$start
                	endline=$end-$start
                	head -n $headline /etc/hotplug/usb.agent.bak > /etc/hotplug/usb.agent	
                        echo                                                >> /etc/hotplug/usb.agent
			echo	"#Change mode for HYP2003 USB Token"	    >> /etc/hotplug/usb.agent 
			echo	"PRO=\`echo \$PRODUCT | cut -d/ -f1\`"      >> /etc/hotplug/usb.agent 
			echo	"if [ \$PRO == \"96e\" ]; then"	 	    >> /etc/hotplug/usb.agent 
			echo	"	while((\$i<100))"	 	    >> /etc/hotplug/usb.agent 
			echo	"	do"			 	    >> /etc/hotplug/usb.agent 
			echo	"		if [ -e \$DEVICE ]; then "  >> /etc/hotplug/usb.agent 
			echo	"			break"		    >> /etc/hotplug/usb.agent 
			echo	"		fi"			    >> /etc/hotplug/usb.agent 
			echo	"		sleep 0.01"	 	    >> /etc/hotplug/usb.agent 
			echo	"	done"			 	    >> /etc/hotplug/usb.agent 
			echo	"chmod +666 \$DEVICE"			    >> /etc/hotplug/usb.agent 
			echo	"fi"					    >> /etc/hotplug/usb.agent 
			echo						    >> /etc/hotplug/usb.agent 
                	tail -n $endline /etc/hotplug/usb.agent.bak         >> /etc/hotplug/usb.agent	
        	else
			start=`cat /etc/hotplug/usb.agent -n | grep "#!/bin/sh" | head -1 | cut -f1`
                        end=`cat /etc/hotplug/usb.agent | wc -l`
                        headline=$start+1
                        endline=$end-$start-1
                        head -n $headline /etc/hotplug/usb.agent.bak > /etc/hotplug/usb.agent
                        echo                                                >> /etc/hotplug/usb.agent
			echo	"#Change mode for HYP2003 USB Token"	    >> /etc/hotplug/usb.agent 
			echo	"PRO=\`echo \$PRODUCT | cut -d/ -f1\`"      >> /etc/hotplug/usb.agent 
			echo	"if [ \$PRO == \"96e\" ]; then"	 	    >> /etc/hotplug/usb.agent 
			echo	"	while((\$i<100))"	 	    >> /etc/hotplug/usb.agent 
			echo	"	do"			 	    >> /etc/hotplug/usb.agent 
			echo	"		if [ -e \$DEVICE ]; then "  >> /etc/hotplug/usb.agent 
			echo	"			break"		    >> /etc/hotplug/usb.agent 
			echo	"		fi"			    >> /etc/hotplug/usb.agent 
			echo	"		sleep 0.01"	 	    >> /etc/hotplug/usb.agent 
			echo	"	done"			 	    >> /etc/hotplug/usb.agent 
			echo	"chmod +666 \$DEVICE"			    >> /etc/hotplug/usb.agent 
			echo	"fi"					    >> /etc/hotplug/usb.agent 
			echo						    >> /etc/hotplug/usb.agent 
                        tail -n $endline /etc/hotplug/usb.agent.bak                   >> /etc/hotplug/usb.agent
		fi
	fi    
else
	if [ -d /etc/udev/rules.d/ ]; then
		echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"096e\", MODE=\"0666\"" > /etc/udev/rules.d/HYP2003_token-1.rules
		echo "BUS==\"usb\", SYSFS{idVendor}==\"096e\", MODE=\"0666\"" > /etc/udev/rules.d/HYP2003_token-2.rules
		echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"2ccf\", MODE=\"0666\"" > /etc/udev/rules.d/HYP2003_token-3.rules
		echo "BUS==\"usb\", SYSFS{idVendor}==\"2ccf\", MODE=\"0666\"" > /etc/udev/rules.d/HYP2003_token-4.rules
		if service udev restart &>/dev/null ;
		then
			echo "Service udev restarted!"
		else
			echo "Please restart your computer if this change of udev rules don't to take effect with replug"                       
		fi		
	else
    		echo Please install hotplug or udev tools!!!
	fi
fi

echo run finished!



