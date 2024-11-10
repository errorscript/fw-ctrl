#!/usr/bin/bash

# Copy fanctrl.py to /usr/local/bin and creates a service to run it
# Adapted from https://gist.github.com/ahmedsadman/2c1f118a02190c868b33c9c71835d706

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

SERVICE_NAME="fw-ctrl"

if [ "$1" = "remove" ]; then

    sudo systemctl stop ${SERVICE_NAME//'.service'/} # remove the extension
    sudo systemctl disable ${SERVICE_NAME//'.service'/}
    rm /usr/local/bin/fw-ctrl
    ectool --interface=lpc led power auto
    ectool --interface=lpc autofanctrl # restore default fan manager
    rm /usr/local/bin/ectool
    rm -rf /home/$(logname)/.config/fw-ctrl
    rm /usr/lib/systemd/system-sleep/fw-ctrl-suspend
    rm /usr/local/bin/fw-ctrl-ui
    rm -rf /usr/local/share/fw-ctrl
    rm /usr/share/applications/fw-ctrl-ui.desktop

    echo "fw-ctrl has been removed successfully from system"
elif [ -z $1 ]; then

    pip3 install -r requirements.txt
    cp ./bin/ectool /usr/local/bin
    cp ./ctrl.py /usr/local/bin/fw-ctrl
    chmod +x /usr/local/bin/fw-ctrl
    chown $(logname):$(logname) /usr/local/bin/fw-ctrl
    mkdir -p /home/$(logname)/.config/fw-ctrl
    cp config.json /home/$(logname)/.config/fw-ctrl/
    chown $(logname):$(logname) /home/$(logname)/.config/fw-ctrl/config.json
    cp ./ctrl-ui.py /usr/local/bin/fw-ctrl-ui
    chmod +x /usr/local/bin/fw-ctrl-ui
    chown $(logname):$(logname) /usr/local/bin/fw-ctrl-ui
    mkdir /usr/local/share/fw-ctrl
    cp logo.svg /usr/local/share/fw-ctrl/fw-ctrl-ui.svg
    cp controlcenter.glade /usr/local/share/fw-ctrl/controlcenter.glade
    sudo cat > /usr/share/applications/fw-ctrl-ui.desktop << EOF
[Desktop Entry]
Name=Framework controller
Icon=/usr/local/share/fw-ctrl/fw-ctrl-ui.svg
Exec=fw-ctrl-ui
Terminal=false
Type=Application
StartupNotify=true
Categories=Settings;

EOF


    # cleaning legacy file
    rm /usr/local/bin/ctrl.py 2> /dev/null || true


    # check if service is active
    IS_ACTIVE=$(sudo systemctl is-active  $SERVICE_NAME)
    if [ "$IS_ACTIVE" == "active" ]; then
        # restart the service
        echo "Service is running"
        echo "Stoping service"
        sudo systemctl stop $SERVICE_NAME
        echo "Service stoped"
    fi

    # create service file
    echo "Creating service file"
    sudo cat > /etc/systemd/system/${SERVICE_NAME//'"'/}.service << EOF
[Unit]
Description=FrameWork General Controller
After=multi-user.target
[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3 /usr/local/bin/fw-ctrl --config /home/$(logname)/.config/fw-ctrl/config.json
ExecStopPost=/bin/bash -c 'ectool led power auto && ectool autofanctrl'
[Install]
WantedBy=multi-user.target

EOF

    # create suspend hooks
    echo "Creating suspend hooks"

    sudo cat > /usr/lib/systemd/system-sleep/fw-ctrl-suspend << EOF
#!/bin/sh
echo \$1 \$2 >> /tmp/suspend.log
case \$1 in
    pre)
        ectool led power auto
        ectool autofanctrl
    ;;
    post) 
        nohup runuser -l $(logname) -c "sleep 2 ; fw-ctrl active"
    ;;
esac

EOF

    # make the suspend hook executable
    sudo chmod +x /usr/lib/systemd/system-sleep/fw-ctrl-suspend

    # restart daemon, enable and start service
    echo "Reloading daemon and enabling service"
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME//'.service'/} # remove the extension
    sudo systemctl start ${SERVICE_NAME//'.service'/}
    echo "Service Started"
else
    echo "Unknown command $1"
    exit
fi
exit 0
