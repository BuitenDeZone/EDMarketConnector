#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from builtins import str
from builtins import object
import sys
from sys import platform
import json
from os import chdir, environ
from os.path import dirname, isdir, join
import re
import html
from time import time, localtime, strftime
import webbrowser

import EDMCLogging
from config import appname, applongname, appversion, appversion_nobuild, copyright, config

if getattr(sys, 'frozen', False):
    # Under py2exe sys.path[0] is the executable name
    if platform == 'win32':
        chdir(dirname(sys.path[0]))
        # Allow executable to be invoked from any cwd
        environ['TCL_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tcl')
        environ['TK_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tk')

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog
import tkinter.font
import tkinter.messagebox
from ttkHyperlinkLabel import HyperlinkLabel

if __debug__:
    if platform != 'win32':
        import pdb
        import signal
        signal.signal(signal.SIGTERM, lambda sig, frame: pdb.Pdb().set_trace(frame))

import companion
import commodity
from commodity import COMMODITY_CSV
import td
import stats
import prefs
import plug
from hotkey import hotkeymgr
from l10n import Translations
from monitor import monitor
from protocol import protocolhandler
from dashboard import dashboard
from theme import theme


SERVER_RETRY = 5  # retry pause for Companion servers [s]

SHIPYARD_HTML_TEMPLATE = """
<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="refresh" content="0; url={link}">
        <title>Redirecting you to your {ship_name} at {provider_name}...</title>
    </head>
    <body>
        <a href="{link}">
            You should be redirected to your {ship_name} at {provider_name} shortly...
        </a>
    </body>
</html>
"""


class AppWindow(object):

    # Tkinter Event types
    EVENT_KEYPRESS = 2
    EVENT_BUTTON = 4
    EVENT_VIRTUAL = 35

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        self.prefsdialog = None

        plug.load_plugins(master)

        if platform != 'darwin':
            if platform == 'win32':
                self.w.wm_iconbitmap(default='EDMarketConnector.ico')
            else:
                self.w.tk.call('wm', 'iconphoto', self.w, '-default', tk.PhotoImage(file=join(config.respath, 'EDMarketConnector.png')))  # noqa: E501
            self.theme_icon = tk.PhotoImage(data='R0lGODlhFAAQAMZQAAoKCQoKCgsKCQwKCQsLCgwLCg4LCQ4LCg0MCg8MCRAMCRANChINCREOChIOChQPChgQChgRCxwTCyYVCSoXCS0YCTkdCTseCT0fCTsjDU0jB0EnDU8lB1ElB1MnCFIoCFMoCEkrDlkqCFwrCGEuCWIuCGQvCFs0D1w1D2wyCG0yCF82D182EHE0CHM0CHQ1CGQ5EHU2CHc3CHs4CH45CIA6CIE7CJdECIdLEolMEohQE5BQE41SFJBTE5lUE5pVE5RXFKNaFKVbFLVjFbZkFrxnFr9oFsNqFsVrF8RsFshtF89xF9NzGNh1GNl2GP+KG////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAUABAAAAeegAGCgiGDhoeIRDiIjIZGKzmNiAQBQxkRTU6am0tPCJSGShuSAUcLoIIbRYMFra4FAUgQAQCGJz6CDQ67vAFJJBi0hjBBD0w9PMnJOkAiJhaIKEI7HRoc19ceNAolwbWDLD8uAQnl5ga1I9CHEjEBAvDxAoMtFIYCBy+kFDKHAgM3ZtgYSLAGgwkp3pEyBOJCC2ELB31QATGioAoVAwEAOw==')  # noqa: E501
            self.theme_minimize = tk.BitmapImage(data='#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfc, 0x3f,\n   0xfc, 0x3f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };\n')  # noqa: E501
            self.theme_close = tk.BitmapImage(data='#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x0c, 0x30, 0x1c, 0x38, 0x38, 0x1c, 0x70, 0x0e,\n   0xe0, 0x07, 0xc0, 0x03, 0xc0, 0x03, 0xe0, 0x07, 0x70, 0x0e, 0x38, 0x1c,\n   0x1c, 0x38, 0x0c, 0x30, 0x00, 0x00, 0x00, 0x00 };\n')  # noqa: E501

        frame = tk.Frame(self.w, name=appname.lower())
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)

        self.cmdr_label = tk.Label(frame)
        self.ship_label = tk.Label(frame)
        self.system_label = tk.Label(frame)
        self.station_label = tk.Label(frame)

        self.cmdr_label.grid(row=1, column=0, sticky=tk.W)
        self.ship_label.grid(row=2, column=0, sticky=tk.W)
        self.system_label.grid(row=3, column=0, sticky=tk.W)
        self.station_label.grid(row=4, column=0, sticky=tk.W)

        self.cmdr = tk.Label(frame, compound=tk.RIGHT, anchor=tk.W, name='cmdr')
        self.ship = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.shipyard_url, name='ship')
        self.system = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.system_url, popup_copy=True, name='system')
        self.station = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.station_url, name='station')

        self.cmdr.grid(row=1, column=1, sticky=tk.EW)
        self.ship.grid(row=2, column=1, sticky=tk.EW)
        self.system.grid(row=3, column=1, sticky=tk.EW)
        self.station.grid(row=4, column=1, sticky=tk.EW)

        for plugin in plug.PLUGINS:
            appitem = plugin.get_app(frame)
            if appitem:
                tk.Frame(frame, highlightthickness=1).grid(columnspan=2, sticky=tk.EW)  # separator
                if isinstance(appitem, tuple) and len(appitem) == 2:
                    row = frame.grid_size()[1]
                    appitem[0].grid(row=row, column=0, sticky=tk.W)
                    appitem[1].grid(row=row, column=1, sticky=tk.EW)
                else:
                    appitem.grid(columnspan=2, sticky=tk.EW)

        # Update button in main window
        self.button = ttk.Button(frame, text=_('Update'), width=28, default=tk.ACTIVE, state=tk.DISABLED)
        self.theme_button = tk.Label(frame, width=32 if platform == 'darwin' else 28, state=tk.DISABLED)
        self.status = tk.Label(frame, name='status', anchor=tk.W)

        row = frame.grid_size()[1]
        self.button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        self.theme_button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        theme.register_alternate((self.button, self.theme_button, self.theme_button), {'row': row, 'columnspan': 2, 'sticky': tk.NSEW})  # noqa: E501
        self.status.grid(columnspan=2, sticky=tk.EW)
        self.button.bind('<Button-1>', self.getandsend)
        theme.button_bind(self.theme_button, self.getandsend)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform != 'win32' or isinstance(child, tk.Frame)) and 2 or 0)

        self.menubar = tk.Menu()
        if platform == 'darwin':
            # Can't handle (de)iconify if topmost is set, so suppress iconify button
            # http://wiki.tcl.tk/13428 and p15 of
            # https://developer.apple.com/legacy/library/documentation/Carbon/Conceptual/HandlingWindowsControls/windowscontrols.pdf
            root.call('tk::unsupported::MacWindowStyle', 'style', root, 'document', 'closeBox resizable')

            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            self.system_menu = tk.Menu(self.menubar, name='apple')
            self.system_menu.add_command(command=lambda: self.w.call('tk::mac::standardAboutPanel'))
            self.system_menu.add_command(command=lambda: self.updater.checkForUpdates())
            self.menubar.add_cascade(menu=self.system_menu)
            self.file_menu = tk.Menu(self.menubar, name='file')
            self.file_menu.add_command(command=self.save_raw)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, name='edit')
            self.edit_menu.add_command(accelerator='Command-c', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.w.bind('<Command-c>', self.copy)
            self.view_menu = tk.Menu(self.menubar, name='view')
            self.view_menu.add_command(command=lambda: stats.StatsDialog(self))
            self.menubar.add_cascade(menu=self.view_menu)
            window_menu = tk.Menu(self.menubar, name='window')
            self.menubar.add_cascade(menu=window_menu)
            self.help_menu = tk.Menu(self.menubar, name='help')
            self.w.createcommand("::tk::mac::ShowHelp", self.help_general)
            self.help_menu.add_command(command=self.help_privacy)
            self.help_menu.add_command(command=self.help_releases)
            self.menubar.add_cascade(menu=self.help_menu)
            self.w['menu'] = self.menubar
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            self.w.call('set', 'tk::mac::useCompatibilityMetrics', '0')
            self.w.createcommand('tkAboutDialog', lambda: self.w.call('tk::mac::standardAboutPanel'))
            self.w.createcommand("::tk::mac::Quit", self.onexit)
            self.w.createcommand("::tk::mac::ShowPreferences", lambda: prefs.PreferencesDialog(self.w, self.postprefs))
            self.w.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)  # click on app in dock = restore
            self.w.protocol("WM_DELETE_WINDOW", self.w.withdraw)  # close button shouldn't quit app
            self.w.resizable(tk.FALSE, tk.FALSE)  # Can't be only resizable on one axis
        else:
            self.file_menu = self.view_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.file_menu.add_command(command=lambda: stats.StatsDialog(self))
            self.file_menu.add_command(command=self.save_raw)
            self.file_menu.add_command(command=lambda: prefs.PreferencesDialog(self.w, self.postprefs))
            self.file_menu.add_separator()
            self.file_menu.add_command(command=self.onexit)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.edit_menu.add_command(accelerator='Ctrl+C', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.help_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.help_menu.add_command(command=self.help_general)
            self.help_menu.add_command(command=self.help_privacy)
            self.help_menu.add_command(command=self.help_releases)
            self.help_menu.add_command(command=lambda: self.updater.checkForUpdates())
            self.help_menu.add_command(command=lambda: not self.HelpAbout.showing and self.HelpAbout(self.w))

            self.menubar.add_cascade(menu=self.help_menu)
            if platform == 'win32':
                # Must be added after at least one "real" menu entry
                self.always_ontop = tk.BooleanVar(value=config.getint('always_ontop'))
                self.system_menu = tk.Menu(self.menubar, name='system', tearoff=tk.FALSE)
                self.system_menu.add_separator()
                self.system_menu.add_checkbutton(label=_('Always on top'),
                                                 variable=self.always_ontop,
                                                 command=self.ontop_changed)  # Appearance setting
                self.menubar.add_cascade(menu=self.system_menu)
            self.w.bind('<Control-c>', self.copy)
            self.w.protocol("WM_DELETE_WINDOW", self.onexit)
            theme.register(self.menubar)  # menus and children aren't automatically registered
            theme.register(self.file_menu)
            theme.register(self.edit_menu)
            theme.register(self.help_menu)

            # Alternate title bar and menu for dark theme
            self.theme_menubar = tk.Frame(frame)
            self.theme_menubar.columnconfigure(2, weight=1)
            theme_titlebar = tk.Label(self.theme_menubar, text=applongname,
                                      image=self.theme_icon, cursor='fleur',
                                      anchor=tk.W, compound=tk.LEFT)
            theme_titlebar.grid(columnspan=3, padx=2, sticky=tk.NSEW)
            self.drag_offset = None
            theme_titlebar.bind('<Button-1>', self.drag_start)
            theme_titlebar.bind('<B1-Motion>', self.drag_continue)
            theme_titlebar.bind('<ButtonRelease-1>', self.drag_end)
            theme_minimize = tk.Label(self.theme_menubar, image=self.theme_minimize)
            theme_minimize.grid(row=0, column=3, padx=2)
            theme.button_bind(theme_minimize, self.oniconify, image=self.theme_minimize)
            theme_close = tk.Label(self.theme_menubar, image=self.theme_close)
            theme_close.grid(row=0, column=4, padx=2)
            theme.button_bind(theme_close, self.onexit, image=self.theme_close)
            self.theme_file_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_file_menu.grid(row=1, column=0, padx=5, sticky=tk.W)
            theme.button_bind(self.theme_file_menu,
                              lambda e: self.file_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            self.theme_edit_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_edit_menu.grid(row=1, column=1, sticky=tk.W)
            theme.button_bind(self.theme_edit_menu,
                              lambda e: self.edit_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            self.theme_help_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_help_menu.grid(row=1, column=2, sticky=tk.W)
            theme.button_bind(self.theme_help_menu,
                              lambda e: self.help_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            tk.Frame(self.theme_menubar, highlightthickness=1).grid(columnspan=5, padx=5, sticky=tk.EW)
            theme.register(self.theme_minimize)  # images aren't automatically registered
            theme.register(self.theme_close)
            self.blank_menubar = tk.Frame(frame)
            tk.Label(self.blank_menubar).grid()
            tk.Label(self.blank_menubar).grid()
            tk.Frame(self.blank_menubar, height=2).grid()
            theme.register_alternate((self.menubar, self.theme_menubar, self.blank_menubar),
                                     {'row': 0, 'columnspan': 2, 'sticky': tk.NSEW})
            self.w.resizable(tk.TRUE, tk.FALSE)

        # update geometry
        if config.get('geometry'):
            match = re.match('\+([\-\d]+)\+([\-\d]+)', config.get('geometry'))  # noqa: W605
            if match:
                if platform == 'darwin':
                    # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
                    if int(match.group(2)) >= 0:
                        self.w.geometry(config.get('geometry'))
                elif platform == 'win32':
                    # Check that the titlebar will be at least partly on screen
                    import ctypes
                    from ctypes.wintypes import POINT
                    # https://msdn.microsoft.com/en-us/library/dd145064
                    MONITOR_DEFAULTTONULL = 0  # noqa: N806
                    if ctypes.windll.user32.MonitorFromPoint(POINT(int(match.group(1)) + 16, int(match.group(2)) + 16),
                                                             MONITOR_DEFAULTTONULL):
                        self.w.geometry(config.get('geometry'))
                else:
                    self.w.geometry(config.get('geometry'))
        self.w.attributes('-topmost', config.getint('always_ontop') and 1 or 0)

        theme.register(frame)
        theme.apply(self.w)

        self.w.bind('<Map>', self.onmap)  # Special handling for overrideredict
        self.w.bind('<Enter>', self.onenter)  # Special handling for transparency
        self.w.bind('<FocusIn>', self.onenter)  # Special handling for transparency
        self.w.bind('<Leave>', self.onleave)  # Special handling for transparency
        self.w.bind('<FocusOut>', self.onleave)  # Special handling for transparency
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)
        self.w.bind_all('<<Invoke>>', self.getandsend)  # Hotkey monitoring
        self.w.bind_all('<<JournalEvent>>', self.journal_event)  # Journal monitoring
        self.w.bind_all('<<DashboardEvent>>', self.dashboard_event)  # Dashboard monitoring
        self.w.bind_all('<<PluginError>>', self.plugin_error)  # Statusbar
        self.w.bind_all('<<CompanionAuthEvent>>', self.auth)  # cAPI auth
        self.w.bind_all('<<Quit>>', self.onexit)  # Updater

        # Start a protocol handler to handle cAPI registration. Requires main loop to be running.
        self.w.after_idle(lambda: protocolhandler.start(self.w))

        # Load updater after UI creation (for WinSparkle)
        import update
        if getattr(sys, 'frozen', False):
            # Running in frozen .exe, so use (Win)Sparkle
            self.updater = update.Updater(tkroot=self.w, provider='external')
        else:
            self.updater = update.Updater(tkroot=self.w, provider='internal')
            self.updater.checkForUpdates()  # Sparkle / WinSparkle does this automatically for packaged apps

        try:
            config.get_password('')  # Prod SecureStorage on Linux to initialise
        except RuntimeError:
            pass

        # Migration from <= 3.30
        for username in config.get('fdev_usernames') or []:
            config.delete_password(username)
        config.delete('fdev_usernames')
        config.delete('username')
        config.delete('password')
        config.delete('logdir')

        self.postprefs(False)  # Companion login happens in callback from monitor

    # callback after the Preferences dialog is applied
    def postprefs(self, dologin=True):
        self.prefsdialog = None
        self.set_labels()  # in case language has changed

        # Reset links in case plugins changed them
        self.ship.configure(url=self.shipyard_url)
        self.system.configure(url=self.system_url)
        self.station.configure(url=self.station_url)

        # (Re-)install hotkey monitoring
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

        # (Re-)install log monitoring
        if not monitor.start(self.w):
            self.status['text'] = f'Error: Check {_("E:D journal file location")}'

        if dologin and monitor.cmdr:
            self.login()  # Login if not already logged in with this Cmdr

    # set main window labels, e.g. after language change
    def set_labels(self):
        self.cmdr_label['text'] = _('Cmdr') + ':'  # Main window
        # Multicrew role label in main window
        self.ship_label['text'] = (monitor.state['Captain'] and _('Role') or _('Ship')) + ':'  # Main window
        self.system_label['text'] = _('System') + ':'  # Main window
        self.station_label['text'] = _('Station') + ':'  # Main window
        self.button['text'] = self.theme_button['text'] = _('Update')  # Update button in main window
        if platform == 'darwin':
            self.menubar.entryconfigure(1, label=_('File'))  # Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))  # Menu title
            self.menubar.entryconfigure(3, label=_('View'))  # Menu title on OSX
            self.menubar.entryconfigure(4, label=_('Window'))  # Menu title on OSX
            self.menubar.entryconfigure(5, label=_('Help'))  # Menu title
            self.system_menu.entryconfigure(0, label=_("About {APP}").format(APP=applongname))  # App menu entry on OSX
            self.system_menu.entryconfigure(1, label=_("Check for Updates..."))  # Menu item
            self.file_menu.entryconfigure(0, label=_('Save Raw Data...'))  # Menu item
            self.view_menu.entryconfigure(0, label=_('Status'))  # Menu item
            self.help_menu.entryconfigure(1, label=_('Privacy Policy'))  # Help menu item
            self.help_menu.entryconfigure(2, label=_('Release Notes'))  # Help menu item
        else:
            self.menubar.entryconfigure(1, label=_('File'))  # Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))  # Menu title
            self.menubar.entryconfigure(3, label=_('Help'))  # Menu title
            self.theme_file_menu['text'] = _('File')  # Menu title
            self.theme_edit_menu['text'] = _('Edit')  # Menu title
            self.theme_help_menu['text'] = _('Help')  # Menu title

            # File menu
            self.file_menu.entryconfigure(0, label=_('Status'))  # Menu item
            self.file_menu.entryconfigure(1, label=_('Save Raw Data...'))  # Menu item
            self.file_menu.entryconfigure(2, label=_('Settings'))  # Item in the File menu on Windows
            self.file_menu.entryconfigure(4, label=_('Exit'))  # Item in the File menu on Windows

            # Help menu
            self.help_menu.entryconfigure(0, label=_('Documentation'))  # Help menu item
            self.help_menu.entryconfigure(1, label=_('Privacy Policy'))  # Help menu item
            self.help_menu.entryconfigure(2, label=_('Release Notes'))  # Help menu item
            self.help_menu.entryconfigure(3, label=_('Check for Updates...'))  # Menu item
            self.help_menu.entryconfigure(4, label=_("About {APP}").format(APP=applongname))  # App menu entry

        # Edit menu
        self.edit_menu.entryconfigure(0, label=_('Copy'))  # As in Copy and Paste

    def login(self):
        if not self.status['text']:
            self.status['text'] = _('Logging in...')
        self.button['state'] = self.theme_button['state'] = tk.DISABLED
        if platform == 'darwin':
            self.view_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Save Raw Data
        else:
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(1, state=tk.DISABLED)  # Save Raw Data
        self.w.update_idletasks()
        try:
            if companion.session.login(monitor.cmdr, monitor.is_beta):
                # Successfully authenticated with the Frontier website
                self.status['text'] = _('Authentication successful')
                if platform == 'darwin':
                    self.view_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                    self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Save Raw Data
                else:
                    self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                    self.file_menu.entryconfigure(1, state=tk.NORMAL)  # Save Raw Data
        except (companion.CredentialsError, companion.ServerError, companion.ServerLagging) as e:
            self.status['text'] = str(e)
        except Exception as e:
            logger.debug('Frontier CAPI Auth', exc_info=e)
            self.status['text'] = str(e)
        self.cooldown()

    def getandsend(self, event=None, retrying=False):

        auto_update = not event
        play_sound = (auto_update or int(event.type) == self.EVENT_VIRTUAL) and not config.getint('hotkey_mute')
        play_bad = False

        if not monitor.cmdr or not monitor.mode or monitor.state['Captain'] or not monitor.system:
            return  # In CQC or on crew - do nothing

        if companion.session.state == companion.Session.STATE_AUTH:
            # Attempt another Auth
            self.login()
            return

        if not retrying:
            if time() < self.holdofftime:  # Was invoked by key while in cooldown
                self.status['text'] = ''
                if play_sound and (self.holdofftime-time()) < companion.holdoff*0.75:
                    hotkeymgr.play_bad()  # Don't play sound in first few seconds to prevent repeats
                return
            elif play_sound:
                hotkeymgr.play_good()
            self.status['text'] = _('Fetching data...')
            self.button['state'] = self.theme_button['state'] = tk.DISABLED
            self.w.update_idletasks()

        try:
            querytime = int(time())
            data = companion.session.station()
            config.set('querytime', querytime)

            # Validation
            if not data.get('commander', {}).get('name'):
                self.status['text'] = _("Who are you?!")  # Shouldn't happen
            elif (not data.get('lastSystem', {}).get('name')
                  or (data['commander'].get('docked')
                      and not data.get('lastStarport', {}).get('name'))):  # Only care if docked
                self.status['text'] = _("Where are you?!")  # Shouldn't happen
            elif not data.get('ship', {}).get('name') or not data.get('ship', {}).get('modules'):
                self.status['text'] = _("What are you flying?!")  # Shouldn't happen
            elif monitor.cmdr and data['commander']['name'] != monitor.cmdr:
                # Companion API return doesn't match Journal
                raise companion.CmdrError()
            elif ((auto_update and not data['commander'].get('docked'))
                  or (data['lastSystem']['name'] != monitor.system)
                  or ((data['commander']['docked']
                       and data['lastStarport']['name'] or None) != monitor.station)
                  or (data['ship']['id'] != monitor.state['ShipID'])
                  or (data['ship']['name'].lower() != monitor.state['ShipType'])):
                raise companion.ServerLagging()

            else:

                if __debug__:  # Recording
                    if isdir('dump'):
                        with open('dump/{system}{station}.{timestamp}.json'.format(
                                system=data['lastSystem']['name'],
                                station=data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '',
                                timestamp=strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wb') as h:
                            h.write(json.dumps(data,
                                               ensure_ascii=False,
                                               indent=2,
                                               sort_keys=True,
                                               separators=(',', ': ')).encode('utf-8'))

                if not monitor.state['ShipType']:  # Started game in SRV or fighter
                    self.ship['text'] = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
                    monitor.state['ShipID'] = data['ship']['id']
                    monitor.state['ShipType'] = data['ship']['name'].lower()

                if data['commander'].get('credits') is not None:
                    monitor.state['Credits'] = data['commander']['credits']
                    monitor.state['Loan'] = data['commander'].get('debt', 0)

                # stuff we can do when not docked
                err = plug.notify_newdata(data, monitor.is_beta)
                self.status['text'] = err and err or ''
                if err:
                    play_bad = True

                # Export market data
                if config.getint('output') & (config.OUT_STATION_ANY):
                    if not data['commander'].get('docked'):
                        if not self.status['text']:
                            # Signal as error because the user might actually be docked
                            # but the server hosting the Companion API hasn't caught up
                            self.status['text'] = _("You're not docked at a station!")
                            play_bad = True
                    # Ignore possibly missing shipyard info
                    elif (config.getint('output') & config.OUT_MKT_EDDN)\
                            and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have anything!")
                    elif not data['lastStarport'].get('commodities'):
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have a market!")
                    elif config.getint('output') & (config.OUT_MKT_CSV | config.OUT_MKT_TD):
                        # Fixup anomalies in the commodity data
                        fixed = companion.fixup(data)
                        if config.getint('output') & config.OUT_MKT_CSV:
                            commodity.export(fixed, COMMODITY_CSV)
                        if config.getint('output') & config.OUT_MKT_TD:
                            td.export(fixed)

                self.holdofftime = querytime + companion.holdoff

        # Companion API problem
        except companion.ServerLagging as e:
            if retrying:
                self.status['text'] = str(e)
                play_bad = True
            else:
                # Retry once if Companion server is unresponsive
                self.w.after(int(SERVER_RETRY * 1000), lambda: self.getandsend(event, True))
                return  # early exit to avoid starting cooldown count

        except companion.CmdrError as e:  # Companion API return doesn't match Journal
            self.status['text'] = str(e)
            play_bad = True
            companion.session.invalidate()
            self.login()

        except Exception as e:  # Including CredentialsError, ServerError
            logger.debug('"other" exception', exc_info=e)
            self.status['text'] = str(e)
            play_bad = True

        if not self.status['text']:  # no errors
            self.status['text'] = strftime(_('Last updated at %H:%M:%S'), localtime(querytime))
        if play_sound and play_bad:
            hotkeymgr.play_bad()

        self.cooldown()

    def retry_for_shipyard(self, tries):
        # Try again to get shipyard data and send to EDDN. Don't report errors if can't get or send the data.
        try:
            data = companion.session.station()
            if data['commander'].get('docked'):
                if data.get('lastStarport', {}).get('ships'):
                    report = 'Success'
                else:
                    report = 'Failure'
            else:
                report = 'Undocked!'
            logger.debug(f'Retry for shipyard - {report}')
            if not data['commander'].get('docked'):
                # might have un-docked while we were waiting for retry in which case station data is unreliable
                pass
            elif (data.get('lastSystem',   {}).get('name') == monitor.system and
                  data.get('lastStarport', {}).get('name') == monitor.station and
                  data.get('lastStarport', {}).get('ships', {}).get('shipyard_list')):
                self.eddn.export_shipyard(data, monitor.is_beta)
            elif tries > 1:  # bogus data - retry
                self.w.after(int(SERVER_RETRY * 1000), lambda: self.retry_for_shipyard(tries-1))
        except Exception:
            pass

    # Handle event(s) from the journal
    def journal_event(self, event):

        def crewroletext(role):
            # Return translated crew role. Needs to be dynamic to allow for changing language.
            return {
                None: '',
                'Idle': '',
                'FighterCon': _('Fighter'),  # Multicrew role
                'FireCon':    _('Gunner'),  # Multicrew role
                'FlightCon':  _('Helm'),  # Multicrew role
            }.get(role, role)

        while True:
            entry = monitor.get_entry()
            if not entry:
                return

            # Update main window
            self.cooldown()
            if monitor.cmdr and monitor.state['Captain']:
                self.cmdr['text'] = f'{monitor.cmdr} / {monitor.state["Captain"]}'
                self.ship_label['text'] = _('Role') + ':'  # Multicrew role label in main window
                self.ship.configure(state=tk.NORMAL, text=crewroletext(monitor.state['Role']), url=None)
            elif monitor.cmdr:
                if monitor.group:
                    self.cmdr['text'] = f'{monitor.cmdr} / {monitor.group}'
                else:
                    self.cmdr['text'] = monitor.cmdr
                self.ship_label['text'] = _('Ship') + ':'  # Main window
                self.ship.configure(
                    text=monitor.state['ShipName']
                    or companion.ship_map.get(monitor.state['ShipType'], monitor.state['ShipType'])
                    or '',
                    url=self.shipyard_url)
            else:
                self.cmdr['text'] = ''
                self.ship_label['text'] = _('Ship') + ':'  # Main window
                self.ship['text'] = ''

            self.edit_menu.entryconfigure(0, state=monitor.system and tk.NORMAL or tk.DISABLED)  # Copy

            if entry['event'] in (
                    'Undocked',
                    'StartJump',
                    'SetUserShipName',
                    'ShipyardBuy',
                    'ShipyardSell',
                    'ShipyardSwap',
                    'ModuleBuy',
                    'ModuleSell',
                    'MaterialCollected',
                    'MaterialDiscarded',
                    'ScientificResearch',
                    'EngineerCraft',
                    'Synthesis',
                    'JoinACrew'):
                self.status['text'] = ''  # Periodically clear any old error
            self.w.update_idletasks()

            # Companion login
            if entry['event'] in [None, 'StartUp', 'NewCommander', 'LoadGame'] and monitor.cmdr:
                if not config.get('cmdrs') or monitor.cmdr not in config.get('cmdrs'):
                    config.set('cmdrs', (config.get('cmdrs') or []) + [monitor.cmdr])
                self.login()

            if not entry['event'] or not monitor.mode:
                return  # Startup or in CQC

            if entry['event'] in ['StartUp', 'LoadGame'] and monitor.started:
                # Disable WinSparkle automatic update checks, IFF configured to do so when in-game
                if config.getint('disable_autoappupdatecheckingame') and 1:
                    self.updater.setAutomaticUpdatesCheck(False)
                    logger.info('Monitor: Disable WinSparkle automatic update checks')
                # Can start dashboard monitoring
                if not dashboard.start(self.w, monitor.started):
                    logger.info("Can't start Status monitoring")

            # Export loadout
            if entry['event'] == 'Loadout' and not monitor.state['Captain']\
                    and config.getint('output') & config.OUT_SHIP:
                monitor.export_ship()

            # Plugins
            err = plug.notify_journal_entry(monitor.cmdr,
                                            monitor.is_beta,
                                            monitor.system,
                                            monitor.station,
                                            entry,
                                            monitor.state)
            if err:
                self.status['text'] = err
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

            # Auto-Update after docking, but not if auth callback is pending
            if entry['event'] in ('StartUp', 'Location', 'Docked')\
                    and monitor.station\
                    and not config.getint('output') & config.OUT_MKT_MANUAL\
                    and config.getint('output') & config.OUT_STATION_ANY\
                    and companion.session.state != companion.Session.STATE_AUTH:
                self.w.after(int(SERVER_RETRY * 1000), self.getandsend)

            if entry['event'] == 'ShutDown':
                # Enable WinSparkle automatic update checks
                # NB: Do this blindly, in case option got changed whilst in-game
                self.updater.setAutomaticUpdatesCheck(True)
                logger.info('Monitor: Enable WinSparkle automatic update checks')

    # cAPI auth
    def auth(self, event=None):
        try:
            companion.session.auth_callback()
            # Successfully authenticated with the Frontier website
            self.status['text'] = _('Authentication successful')
            if platform == 'darwin':
                self.view_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Save Raw Data
            else:
                self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                self.file_menu.entryconfigure(1, state=tk.NORMAL)  # Save Raw Data
        except companion.ServerError as e:
            self.status['text'] = str(e)
        except Exception as e:
            logger.debug('Frontier CAPI Auth:', exc_info=e)
            self.status['text'] = str(e)
        self.cooldown()

    # Handle Status event
    def dashboard_event(self, event):
        entry = dashboard.status
        if entry:
            # Currently we don't do anything with these events
            err = plug.notify_dashboard_entry(monitor.cmdr, monitor.is_beta, entry)
            if err:
                self.status['text'] = err
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

    # Display asynchronous error from plugin
    def plugin_error(self, event=None):
        if plug.last_error.get('msg'):
            self.status['text'] = plug.last_error['msg']
            self.w.update_idletasks()
            if not config.getint('hotkey_mute'):
                hotkeymgr.play_bad()

    def shipyard_url(self, shipname):
        if not bool(config.getint("use_alt_shipyard_open")):
            return plug.invoke(config.get('shipyard_provider'), 'EDSY', 'shipyard_url', monitor.ship(), monitor.is_beta)

        # Avoid file length limits if possible
        provider = config.get('shipyard_provider') or 'EDSY'
        target = plug.invoke(config.get('shipyard_provider'), 'EDSY', 'shipyard_url', monitor.ship(), monitor.is_beta)
        file_name = join(config.app_dir, "last_shipyard.html")

        with open(file_name, 'w') as f:
            print(SHIPYARD_HTML_TEMPLATE.format(
                link=html.escape(str(target)),
                provider_name=html.escape(str(provider)),
                ship_name=html.escape(str(shipname))
            ), file=f)

        return f'file://localhost/{file_name}'

    def system_url(self, system):
        return plug.invoke(config.get('system_provider'),   'EDSM', 'system_url', monitor.system)

    def station_url(self, station):
        return plug.invoke(config.get('station_provider'),  'eddb', 'station_url', monitor.system, monitor.station)

    def cooldown(self):
        if time() < self.holdofftime:
            # Update button in main window
            self.button['text'] = self.theme_button['text'] \
                = _('cooldown {SS}s').format(SS=int(self.holdofftime - time()))
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = self.theme_button['text'] = _('Update')  # Update button in main window
            self.button['state'] = self.theme_button['state'] = (monitor.cmdr and
                                                                 monitor.mode and
                                                                 not monitor.state['Captain'] and
                                                                 monitor.system and
                                                                 tk.NORMAL or tk.DISABLED)

    def ontop_changed(self, event=None):
        config.set('always_ontop', self.always_ontop.get())
        self.w.wm_attributes('-topmost', self.always_ontop.get())

    def copy(self, event=None):
        if monitor.system:
            self.w.clipboard_clear()
            self.w.clipboard_append(monitor.station and f'{monitor.system},{monitor.station}' or monitor.system)

    def help_general(self, event=None):
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/wiki')

    def help_privacy(self, event=None):
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/wiki/Privacy-Policy')

    def help_releases(self, event=None):
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/releases')

    class HelpAbout(tk.Toplevel):
        showing = False

        def __init__(self, parent):
            if self.__class__.showing:
                return
            self.__class__.showing = True

            tk.Toplevel.__init__(self, parent)

            self.parent = parent
            self.title(_('About {APP}').format(APP=applongname))

            if parent.winfo_viewable():
                self.transient(parent)

            # position over parent
            # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            if platform != 'darwin' or parent.winfo_rooty() > 0:
                self.geometry(f'+{parent.winfo_rootx():d}+{parent.winfo_rooty():d}')

            # remove decoration
            if platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            self.resizable(tk.FALSE, tk.FALSE)

            frame = ttk.Frame(self)
            frame.grid(sticky=tk.NSEW)

            row = 1
            ############################################################
            # applongname
            self.appname_label = tk.Label(frame, text=applongname)
            self.appname_label.grid(row=row, columnspan=3, sticky=tk.EW)
            row += 1
            ############################################################

            ############################################################
            # version <link to changelog>
            ttk.Label(frame).grid(row=row, column=0)        # spacer
            row += 1
            self.appversion_label = tk.Label(frame, text=appversion)
            self.appversion_label.grid(row=row, column=0, sticky=tk.E)
            self.appversion = HyperlinkLabel(frame, compound=tk.RIGHT, text=_('Release Notes'),
                                             url='https://github.com/EDCD/EDMarketConnector/releases/tag/Release/'
                                                 f'{appversion_nobuild}',
                                             underline=True)
            self.appversion.grid(row=row, column=2, sticky=tk.W)
            row += 1
            ############################################################

            ############################################################
            # <whether up to date>
            ############################################################

            ############################################################
            # <copyright>
            ttk.Label(frame).grid(row=row, column=0)        # spacer
            row += 1
            self.copyright = tk.Label(frame, text=copyright)
            self.copyright.grid(row=row, columnspan=3, sticky=tk.EW)
            row += 1
            ############################################################

            ############################################################
            # OK button to close the window
            ttk.Label(frame).grid(row=row, column=0)        # spacer
            row += 1
            button = ttk.Button(frame, text=_('OK'), command=self.apply)
            button.grid(row=row, column=2, sticky=tk.E)
            button.bind("<Return>", lambda event: self.apply())
            self.protocol("WM_DELETE_WINDOW", self._destroy)
            ############################################################

            logger.info(f'Current version is {appversion}')

        def apply(self):
            self._destroy()

        def _destroy(self):
            self.parent.wm_attributes('-topmost', config.getint('always_ontop') and 1 or 0)
            self.destroy()
            self.__class__.showing = False

    def save_raw(self):
        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()

        try:
            data = companion.session.station()
            self.status['text'] = ''
            default_extension: str = ''
            if platform == 'darwin':
                default_extension = '.json'
            last_system: str = data.get("lastSystem", {}).get("name", "Unknown")
            last_starport: str = ''
            if data['commander'].get('docked'):
                last_starport = '.'+data.get('lastStarport', {}).get('name', 'Unknown')
            timestamp: str = strftime('%Y-%m-%dT%H.%M.%S', localtime())
            f = tkinter.filedialog.asksaveasfilename(parent=self.w,
                                                     defaultextension=default_extension,
                                                     filetypes=[('JSON', '.json'), ('All Files', '*')],
                                                     initialdir=config.get('outdir'),
                                                     initialfile=f'{last_system}{last_starport}.{timestamp}')
            if f:
                with open(f, 'wb') as h:
                    h.write(json.dumps(data,
                                       ensure_ascii=False,
                                       indent=2,
                                       sort_keys=True,
                                       separators=(',', ': ')).encode('utf-8'))
        except companion.ServerError as e:
            self.status['text'] = str(e)
        except Exception as e:
            logger.debug('"other" exception', exc_info=e)
            self.status['text'] = str(e)

    def onexit(self, event=None):
        # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
        if platform != 'darwin' or self.w.winfo_rooty() > 0:
            config.set('geometry', '+{1}+{2}'.format(*self.w.geometry().split('+')))
        self.w.withdraw()  # Following items can take a few seconds, so hide the main window while they happen
        protocolhandler.close()
        hotkeymgr.unregister()
        dashboard.close()
        monitor.close()
        plug.notify_stop()
        self.updater.close()
        companion.session.close()
        config.close()
        self.w.destroy()

    def drag_start(self, event):
        self.drag_offset = (event.x_root - self.w.winfo_rootx(), event.y_root - self.w.winfo_rooty())

    def drag_continue(self, event):
        if self.drag_offset:
            offset_x = event.x_root - self.drag_offset[0]
            offset_y = event.y_root - self.drag_offset[1]
            self.w.geometry(f'+{offset_x:d}+{offset_y:d}')

    def drag_end(self, event):
        self.drag_offset = None

    def oniconify(self, event=None):
        self.w.overrideredirect(0)  # Can't iconize while overrideredirect
        self.w.iconify()
        self.w.update_idletasks()  # Size and windows styles get recalculated here
        self.w.wait_visibility()  # Need main window to be re-created before returning
        theme.active = None  # So theme will be re-applied on map

    def onmap(self, event=None):
        if event.widget == self.w:
            theme.apply(self.w)

    def onenter(self, event=None):
        if config.getint('theme') > 1:
            self.w.attributes("-transparentcolor", '')
            self.blank_menubar.grid_remove()
            self.theme_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)

    def onleave(self, event=None):
        if config.getint('theme') > 1 and event.widget == self.w:
            self.w.attributes("-transparentcolor", 'grey4')
            self.theme_menubar.grid_remove()
            self.blank_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)


def enforce_single_instance() -> None:
    # Ensure only one copy of the app is running under this user account. OSX does this automatically. Linux TODO.
    if platform == 'win32':
        import ctypes
        from ctypes.wintypes import HWND, LPWSTR, LPCWSTR, INT, BOOL, LPARAM
        EnumWindows = ctypes.windll.user32.EnumWindows  # noqa: N806
        GetClassName = ctypes.windll.user32.GetClassNameW  # noqa: N806
        GetClassName.argtypes = [HWND, LPWSTR, ctypes.c_int]  # noqa: N806
        GetWindowText = ctypes.windll.user32.GetWindowTextW  # noqa: N806
        GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]  # noqa: N806
        GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW  # noqa: N806
        GetProcessHandleFromHwnd = ctypes.windll.oleacc.GetProcessHandleFromHwnd  # noqa: N806

        SW_RESTORE = 9  # noqa: N806
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow  # noqa: N806
        ShowWindow = ctypes.windll.user32.ShowWindow  # noqa: N806
        ShowWindowAsync = ctypes.windll.user32.ShowWindowAsync  # noqa: N806

        COINIT_MULTITHREADED = 0  # noqa: N806,F841
        COINIT_APARTMENTTHREADED = 0x2  # noqa: N806
        COINIT_DISABLE_OLE1DDE = 0x4  # noqa: N806
        CoInitializeEx = ctypes.windll.ole32.CoInitializeEx  # noqa: N806

        ShellExecute = ctypes.windll.shell32.ShellExecuteW  # noqa: N806
        ShellExecute.argtypes = [HWND, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, INT]

        def window_title(h):
            if h:
                text_length = GetWindowTextLength(h) + 1
                buf = ctypes.create_unicode_buffer(text_length)
                if GetWindowText(h, buf, text_length):
                    return buf.value
            return None

        @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
        def enumwindowsproc(window_handle, l_param):
            # class name limited to 256 - https://msdn.microsoft.com/en-us/library/windows/desktop/ms633576
            cls = ctypes.create_unicode_buffer(257)
            if GetClassName(window_handle, cls, 257)\
                    and cls.value == 'TkTopLevel'\
                    and window_title(window_handle) == applongname\
                    and GetProcessHandleFromHwnd(window_handle):
                # If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                if len(sys.argv) > 1 and sys.argv[1].startswith(protocolhandler.redirect):
                    # Browser invoked us directly with auth response. Forward the response to the other app instance.
                    CoInitializeEx(0, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE)
                    # Wait for it to be responsive to avoid ShellExecute recursing
                    ShowWindow(window_handle, SW_RESTORE)
                    ShellExecute(0, None, sys.argv[1], None, None, SW_RESTORE)
                else:
                    ShowWindowAsync(window_handle, SW_RESTORE)
                    SetForegroundWindow(window_handle)
                sys.exit(0)
            return True

        EnumWindows(enumwindowsproc, 0)


def test_logging():
    logger.debug('Test from EDMarketConnector.py top-level test_logging()')


# Run the app
if __name__ == "__main__":
    # Keep this as the very first code run to be as sure as possible of no
    # output until after this redirect is done, if needed.
    if getattr(sys, 'frozen', False):
        # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
        import tempfile
        # unbuffered not allowed for text in python3, so use `1 for line buffering
        sys.stdout = sys.stderr = open(join(tempfile.gettempdir(), f'{appname}.log'), mode='wt', buffering=1)

    enforce_single_instance()

    logger = EDMCLogging.Logger(appname).get_logger()

    # TODO: unittests in place of these
    # logger.debug('Test from __main__')
    # test_logging()
    class A(object):
        class B(object):
            def __init__(self):
                logger.debug('A call from A.B.__init__')

    # abinit = A.B()

    # Plain, not via `logger`
    print(f'{applongname} {appversion}')

    Translations.install(config.get('language') or None)  # Can generate errors so wait til log set up

    root = tk.Tk(className=appname.lower())
    app = AppWindow(root)

    def messagebox_not_py3():
        plugins_not_py3_last = config.getint('plugins_not_py3_last') or 0
        if (plugins_not_py3_last + 86400) < int(time()) and len(plug.PLUGINS_not_py3):
            # Yes, this is horribly hacky so as to be sure we match the key
            # that we told Translators to use.
            popup_text = "One or more of your enabled plugins do not yet have support for Python 3.x. Please see the " \
                         "list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an " \
                         "updated version available, else alert the developer that they need to update the code for " \
                         "Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on " \
                         "the end of the name."
            popup_text = popup_text.replace('\n', '\\n')
            popup_text = popup_text.replace('\r', '\\r')
            # Now the string should match, so try translation
            popup_text = _(popup_text)
            # And substitute in the other words.
            popup_text = popup_text.format(PLUGINS=_('Plugins'), FILE=_('File'), SETTINGS=_('Settings'), DISABLED='.disabled')
            # And now we do need these to be actual \r\n
            popup_text = popup_text.replace('\\n', '\n')
            popup_text = popup_text.replace('\\r', '\r')

            tk.messagebox.showinfo(
                _('EDMC: Plugins Without Python 3.x Support'),
                popup_text
            )
            config.set('plugins_not_py3_last', int(time()))

    root.after(0, messagebox_not_py3)
    root.mainloop()
