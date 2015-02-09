#!/usr/bin/env python3

import sys
import configparser
import sched
import time
import multiprocessing as mp
import threading as thr
import os
import re

import PyQt5.QtWidgets
import PyQt5.QtCore
import PyQt5.QtGui

import requests


def make_screenshot(cfg, to_sched):
    app2 = PyQt5.QtGui.QGuiApplication([])
    screen = PyQt5.QtWidgets.QApplication.primaryScreen()
    if screen is not None:
        originalPixmap = screen.grabWindow(0)
    else:
        originalPixmap = PyQt5.QtGui.QPixmap()
    fformat = cfg.get('Section', 'format', fallback='png')
    path = cfg.get('Section', 'path', fallback=PyQt5.QtCore.QDir.currentPath())
    if path == '':
        path = PyQt5.QtCore.QDir.currentPath()
    filename = os.path.join(path, (str(int(time.mktime(time.localtime())))+"." + fformat))
    try:
        originalPixmap.save(filename, fformat)
    except Exception as e:
        message = {'title' : 'Failed to save file!',
                   'body' : str(e),
                   'severity' : 3,
                   'timeout' : 6000
                   }
        to_sched.send(('message', message))
        filename = None
    #app2.exec_()
    #app2.exit(0)
    del app2
    return filename

def send_screenshot(cfg, img, to_sched):
    url = cfg.get('Section', 'url', fallback='')
    if url == '':
        message = {'title' : 'File saved!',
                   'body' : 'File '+os.path.basename(img)+' saved locally, though url not specified so not sending',
                   'severity' : 1,
                   'timeout' : 4000}
        to_sched.send(('message', message))
        return
    kwargs = {files : {'file' : (os.path.basename(img), open(img, 'rb'))},
              }
    if cfg.get('Section', 'user', fallback='') != '':
        kwargs['auth'] = requests.auth.HTTPBasicAuth(cfg.get('Section', 'user', fallback=''), cfg.get('Section', 'password', fallback=''))
    try:
        r = requests.post(url, **kwargs)
    except requests.exceptions.RequestException as e:
        message = {'title' : 'Failed to send file!',
                   'body' : str(e),
                   'severity' : 3,
                   'timeout' : 6000}
        to_sched.send(('message', message))
        return
    if r.status_code == requests.codes.ok:
        message = {'title' : 'File saved and sent!',
                   'body' : 'Successfully send file '+os.path.basename(img),
                   'severity' : 1,
                   'timeout' : 4000}
        to_sched.send(('message', message))
    else:
        message = {'title' : 'Failed to send file!',
                   'body' : 'Remote erver responded '+r.status_code,
                   'severity' : 3,
                   'timeout' : 6000}
        to_sched.send(('message', message))
    return

def make_action(cfg, scheduler, to_sched, to_gui):
    filename = make_screenshot(cfg, to_gui)
    scheduler.enter(int(cfg.get('Section', 'timeout', fallback='5')), 1, make_action, argument=(cfg, scheduler, to_sched, to_gui))
    to_sched.send('run that fucking scheduler!')
    if filename != None:
        send_screenshot(cfg, filename, to_gui)
    #scheduler.run()
    return

def scheduler_process(stop_e, scheduler, to_sched):
    while not stop_e.is_set():
        if to_sched.poll():
            got_obj = to_sched.recv()
            scheduler.run()
            

def new_process(from_gui, stop_e):
    scheduler = sched.scheduler(time.time, time.sleep)
    cfg = None
    to_sched, to_sched2 = mp.Pipe()
    sched_thread = thr.Thread(target=scheduler_process, args=(stop_e, scheduler, to_sched))
    sched_thread.start()
    while not stop_e.is_set():
        if from_gui.poll(1):
            got_obj = from_gui.recv()
            if got_obj[0] == 'config':
                if cfg is None:
                    cfg = got_obj[1]
                    scheduler.enter(int(cfg.get('Section', 'timeout', fallback='5')), 1, make_action, argument=(cfg, scheduler, to_sched2, from_gui))
                else:
                    cfg = got_obj[1]
                to_sched2.send('run forest run')

def init():
    global cfg
    cfg = configparser.ConfigParser()
    try:
        f = open('pyautoscreenshooter.cfg', 'r')
    except FileNotFoundError:
        #print('You have no config file!')
        #sys.exit()
        pass
    else:
        cfg.read_file(f)
        f.close()
    from_gui, from_mp = mp.Pipe()
    global stop_e
    stop_e = mp.Event()
    stop_e.clear()
    p = mp.Process(target=new_process, args=(from_gui, stop_e))
    p.start()
    from_mp.send(('config', cfg))
    return stop_e, from_mp


class SettingsMenu(PyQt5.QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        global cfg
        self.setWindowTitle("Settings")
        #self.resize(300, 200)
        self.mainlabel = PyQt5.QtWidgets.QLabel('')
        timeoutlabel = PyQt5.QtWidgets.QLabel('Таймаут:')
        self.timeouttext = PyQt5.QtWidgets.QLineEdit()
        self.timeouttext.insert(cfg.get('Section', 'timeout', fallback='60'))
        self.timeouttext.setFixedWidth(100)
        
        pathlabel = PyQt5.QtWidgets.QLabel('Путь к скринам:')
        self.pathtext = PyQt5.QtWidgets.QLineEdit()
        self.pathtext.setFixedWidth(250)
        self.pathbutton = PyQt5.QtWidgets.QPushButton('Browse')
        self.pathbutton.clicked.connect(self.filedialog)
        pathlayout = PyQt5.QtWidgets.QHBoxLayout()
        pathlayout.addWidget(self.pathtext)
        pathlayout.addWidget(self.pathbutton)
        
        urllabel = PyQt5.QtWidgets.QLabel('URL сервера:')
        self.urltext = PyQt5.QtWidgets.QLineEdit()
        self.urltext.insert(cfg.get('Section', 'url', fallback=''))
        userlabel = PyQt5.QtWidgets.QLabel('Логин:')
        self.usertext = PyQt5.QtWidgets.QLineEdit()
        self.usertext.insert(cfg.get('Section', 'user', fallback=''))
        passwordlabel = PyQt5.QtWidgets.QLabel('Пароль:')
        self.passwordtext = PyQt5.QtWidgets.QLineEdit()
        self.timeouttext.insert(cfg.get('Section', 'password', fallback=''))

        mainlayout = PyQt5.QtWidgets.QGridLayout()
        mainlayout.addWidget(self.mainlabel, 0, 0, 1, 2)
        mainlayout.addWidget(timeoutlabel, 1, 0)
        mainlayout.addWidget(self.timeouttext, 1, 1)
        mainlayout.addWidget(pathlabel, 2, 0)
        mainlayout.addLayout(pathlayout, 2, 1)
        mainlayout.addWidget(urllabel, 3, 0)
        mainlayout.addWidget(self.urltext, 3, 1)
        mainlayout.addWidget(userlabel, 4, 0)
        mainlayout.addWidget(self.usertext, 4, 1)
        mainlayout.addWidget(passwordlabel, 5, 0)
        mainlayout.addWidget(self.passwordtext, 5, 1)

        self.submitbutton = PyQt5.QtWidgets.QPushButton('SUBMIT')
        self.submitbutton.clicked.connect(self.submit_data)
        self.cancelbutton = PyQt5.QtWidgets.QPushButton('CANCEL')
        self.cancelbutton.clicked.connect(self.close_window)

        mainlayout.addWidget(self.submitbutton, 6, 0)
        mainlayout.addWidget(self.cancelbutton, 6, 1)

        self.setLayout(mainlayout)

    def filedialog(self):
        path = self.pathtext.text()
        if path == '':
            path = PyQt5.QtCore.QDir.currentPath()
        directorydialog = PyQt5.QtWidgets.QFileDialog(self, 'Set directory', path)
        directorydialog.setFileMode(PyQt5.QtWidgets.QFileDialog.Directory)
        directorydialog.setOption(PyQt5.QtWidgets.QFileDialog.ShowDirsOnly, True)
        directorydialog.fileSelected.connect(self.setdirname)
        directorydialog.show()
        return

    def setdirname(self, dirname):
        self.pathtext.setText(dirname)
    
    def submit_data(self):
        try:
            timeout = int(self.timeouttext.text())
        except ValueError:
            self.mainlabel.setText('Incorrect timeout!')
            return
        if timeout <= 0:
            self.mainlabel.setText('Incorrect timeout!')
            return
        url = self.urltext.text()
        match = re.search(r'(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))', url)        
        if url != '' and (match is None or match.group(0) != url):
            self.mainlabel.setText('Incorrect url!')
            return
        path = self.pathtext.text()
        user = self.usertext.text()
        password = self.passwordtext.text()
        if not cfg.has_section('Section'):
            cfg.add_section('Section')
        cfg.set('Section', 'timeout', str(timeout))
        cfg.set('Section', 'path', path)
        cfg.set('Section', 'url', url)
        cfg.set('Section', 'user', user)
        cfg.set('Section', 'password', password)
        self.mainlabel.setText('Settings are submitted!')
        global cfg_update
        cfg_update.emit()
        return

    def close_window(self):
        self.close()


class ContextMenu(PyQt5.QtWidgets.QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.cfg_update=cfg_update
        
        self.settings_action = self.addAction('Settings')
        self.settings_action.triggered.connect(self.display_settings_menu)
        self.exit_action = self.addAction('Exit')
        self.exit_action.triggered.connect(self.exit_f)

    def display_settings_menu(self, event):
        self.settings_menu = SettingsMenu()
        self.settings_menu.show()
    
    def exit_f(self, event):
        global stop_e
        stop_e.set()
        global app
        app.exit()


class TrayIcon(PyQt5.QtWidgets.QSystemTrayIcon):
    
    message_got = PyQt5.QtCore.pyqtSignal([dict])
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        global cfg_update
        cfg_update = None
        
        self.message_got.connect(self.message_received)
        self.setIcon(PyQt5.QtGui.QIcon('icon.xpm'))
        self.setToolTip('pyautoscreenshooter')
        self.setContextMenu(ContextMenu())

    def message_received(self, message):
        if 'cfg_update' in message:
            global cfg_update
            cfg_update = message['cfg_update']
            return
        if self.supportsMessages():
            if message['severity'] == 0:
                message_icon = self.NoIcon
            elif message['severity'] == 1:
                message_icon = self.Information
            elif message['severity'] == 2:
                message_icon = self.Warning
            elif message['severity'] == 3:
                message_icon = self.Critical
            self.showMessage(message['title'], message['body'], icon=message_icon, msecs=message['timeout'])

class gui_control_thread(PyQt5.QtCore.QThread):

    cfg_update = PyQt5.QtCore.pyqtSignal()

    def __init__(self, stop_e, from_mp, message_got):
        super().__init__()    
        self.stop_e = stop_e
        self.from_mp = from_mp
        self.message_got = message_got

        self.cfg_update.connect(self.send_cfg)
        message_got.emit({'cfg_update':self.cfg_update})
        
    def run(self):
        while not self.stop_e.is_set():
            if self.from_mp.poll():
                recv_obj = self.from_mp.recv()
                if recv_obj[0] == 'message':
                    self.message_got.emit(recv_obj[1])
        return

    def send_cfg(self):
        global cfg
        self.from_mp.send(('config', cfg))
    

if __name__ == '__main__':
    stop_e, from_mp = init()
    global app
    app = PyQt5.QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tray_icon = TrayIcon()
    p = gui_control_thread(stop_e, from_mp, tray_icon.message_got)
    #w = qtwidget(p, tray_icon)
    #tray_icon.connect(p, QtCore.SIGNAL("message_received(QDict)"), tray_icon.message_received)
    tray_icon.show()
    p.start()
    app.exec_()
    sys.exit()
