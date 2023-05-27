#!/bin/bash
# ###########################################
# SCRIPT : DOWNLOAD AND INSTALL YouTube
# ###########################################
#
# Command: wget https://raw.githubusercontent.com/fairbird/Youtube-Opensource-DreamOS/master/installer.sh -qO - | /bin/sh
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
    Packagescodecs=python3-codecs
    Packagecore=python3-core
    Packagejson=python3-json
    Packagenetclient=python3-netclient
    Packagepyopenssl=python3-pyopenssl
    Packagetwistedweb=python3-twisted-web
else
    echo ":You have Python2 image ..."
    sleep 1
    Packagegettext=gettext
    Packagescodecs=python-codecs
    Packagecore=python-core
    Packagejson=python-json
    Packagenetclient=python-netclient
    Packagepyopenssl=python-pyopenssl
    Packagetwistedweb=python-twisted-web
fi

# check depends packges if installed
install $Packagegettext
install $Packagescodecs
install $Packagecore
install $Packagejson
install $Packagenetclient
install $Packagepyopenssl
install $Packagetwistedweb

#########################
# Remove old version
if [ $OSTYPE = "Opensource" ]; then
    opkg remove enigma2-plugin-extensions-youtube
else
    apt remove enigma2-plugin-extensions-youtube -y
fi
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
repo_url="https://github.com/fairbird/Youtube-Opensource-DreamOS/commits/master/src"
hashfile="/usr/lib/enigma2/python/Plugins/Extensions/YouTube/.hashfile"
[ ! $hashfile ] && touch $hashfile
wget -q -O- $repo_url | sed -ne 's#.*data-url="/fairbird/Youtube-Opensource-DreamOS/commits/\([^$<]*\)/commits_list_item".*#\1#p' | cut -d "=" -f2 | head -n 1 > $hashfile
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
