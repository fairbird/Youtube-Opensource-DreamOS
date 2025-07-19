#!/bin/bash
# ###########################################
# SCRIPT : DOWNLOAD AND INSTALL YouTube
# ###########################################
#
# Command: wget https://raw.githubusercontent.com/fairbird/Youtube-Opensource-DreamOS/master/installer.sh -O - | /bin/sh
#
# ###########################################

###########################################
# Configure where we can find things here #
TMPDIR='/tmp'
PLUGINDIR='/usr/lib/enigma2/python/Plugins/Extensions'

#######################
# Remove Old Version #
rm -rf $PLUGINDIR/YouTube
rm -rf $TMPDIR/*master*

#########################
if [ -f /etc/opkg/opkg.conf ]; then
    STATUS='/var/lib/opkg/status'
    OSTYPE='Opensource'
    OPKG='opkg update'
    OPKGINSTAL='opkg install'
elif [ -f /etc/apt/apt.conf ]; then
    STATUS='/var/lib/dpkg/status'
    OSTYPE='DreamOS'
    OPKG='apt-get update'
    OPKGINSTAL='apt-get install'
fi

#########################
install() {
    if grep -qs "Package: $1" $STATUS; then
        echo
    else
        $OPKG >/dev/null 2>&1
        echo "   >>>>   Need to install $1   <<<<"
        echo
        if [ $OSTYPE = "Opensource" ]; then
            $OPKGINSTAL "$1"
            sleep 1
        elif [ $OSTYPE = "DreamOS" ]; then
            $OPKGINSTAL "$1" -y
            sleep 1
        fi
    fi
}

#########################
if [ -f /usr/bin/python3 ] ; then
    echo ":You have Python3 image ..."
    sleep 1
    Packagegettext=gettext
    Packagecore=python3-core
    Packagejson=python3-json
    Packageio=python3-io
    Packageemail=python3-email
    Packagedatetime=python3-datetime
    Packagerequests=python3-requests
else
    echo ":You have Python2 image ..."
    sleep 1
    Packagegettext=gettext
    Packagecore=python-core
    Packagejson=python-json
    Packageio=python-io
    Packageemail=python-email
    Packagedatetime=python-datetime
    Packagerequests=python-requests
fi

# check depends packges if installed
install $Packagegettext
install $Packagecore
install $Packagejson
install $Packageio
install $Packageemail
install $Packagedatetime
install $Packagerequests

#########################
# Remove old version
if [ $OSTYPE = "Opensource" ]; then
    opkg remove enigma2-plugin-extensions-youtube
else
    apt remove enigma2-plugin-extensions-youtube -y
fi
#########################
# Final check depends packges if installed
if ! grep -qs "Package: $Packagegettext" cat $STATUS ; then
	installed='NoPackagegettext'
fi
if ! grep -qs "Package: $Packagecore" cat $STATUS ; then
	installed='NoPackagecore'
fi
if ! grep -qs "Package: $Packagejson" cat $STATUS ; then
	installed='NoPackagejson'
fi
if ! grep -qs "Package: $Packageio" cat $STATUS ; then
	installed='NoPackageio'
fi
if ! grep -qs "Package: $Packageemail" cat $STATUS ; then
	installed='NoPackageemail'
fi
if ! grep -qs "Package: $Packagedatetime" cat $STATUS ; then
	installed='NoPackagedatetime'
fi
if ! grep -qs "Package: $Packagerequests" cat $STATUS ; then
	installed='Packagerequests'
fi
#if [ "$installed" = "NoPackagegettext" -o "$installed" = "NoPackagecore" -o "$installed" = "NoPackagejson" -o "$installed" = "NoPackageio" -o "$installed" = "NoPackageemail" -o "$installed" = "NoPackagedatetime" ]; then
#	rm -r $PLUGINDIR/YouTube > /dev/null 2>&1
#	exit 1
#fi
#########################
cd $TMPDIR
set -e
echo "Downloading And Insallling YouTube plugin Please Wait ......"
echo
wget https://github.com/fairbird/Youtube-Opensource-DreamOS/archive/refs/heads/master.tar.gz -qP $TMPDIR
tar -xzf master.tar.gz
mkdir -p $PLUGINDIR/YouTube
cd Youtube-Opensource-DreamOS-master
python compilelang.py > /dev/null 2>&1
cd ..
cp -rf Youtube-Opensource-DreamOS-master/src/* $PLUGINDIR/YouTube
rm -rf *master*
set +e
cd ..
#########################
# Add latest hash commit
repo_url="https://api.github.com/repos/fairbird/Youtube-Opensource-DreamOS/git/refs/heads/master"
hashfile="/usr/lib/enigma2/python/Plugins/Extensions/YouTube/.hashfile"
[ ! $hashfile ] && touch $hashfile
wget -q -O- $repo_url | awk -F "commits/" '{print $2}' | awk '{ print substr( $0, 1, length($0)-3 ) }' > $hashfile
#########################

sleep 1
echo "#########################################################"
echo "#           YouTube INSTALLED SUCCESSFULLY              #"
echo "#                 Taapat  &  RAED                       #"
echo "#########################################################"
echo "#           your Device will RESTART Now                #"
echo "#########################################################"

if [ $OSTYPE = "Opensource" ]; then
    killall -9 enigma2
else
    systemctl restart enigma2
fi

exit 0
