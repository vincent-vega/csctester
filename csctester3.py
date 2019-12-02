#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__  = 'Davide Barelli'
__version__ = '2.1.1'
__user__    = [ 'Davide', 'Barelli' ]

'''
TODO List
=========

* set default PIN by regex
* send OTP only when requested

BUGS
* exit with value 1 if no signature has been performed with check command (even without errors, e.g. invalid credentials)
* show message for quitting TUI

'''

import curses.textpad as textpad
from collections import OrderedDict
from operator import itemgetter
from logging.handlers import TimedRotatingFileHandler
import base64
import click
import copy
import curses
import getpass
import json
import logging
import os
#import pudb; pu.db
import re
import requests
import shutil
import signal
#import ssl
import sys
import tempfile
import traceback

class GlobalAttributes:
    pass
_priv_attr = GlobalAttributes()
_priv_attr.colorize = True

def get_logger(log_file_name=None):
    global _priv_attr
    logger = logging.getLogger(__name__)
    if log_file_name:
        handler = TimedRotatingFileHandler(log_file_name, when='midnight', interval=1, backupCount=15, encoding='utf-8')
        handler.suffix = '%Y-%m-%d.log'
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        _priv_attr.colorize = False
        logger.setLevel(logging.INFO)
    else:
        handler = logging.StreamHandler(sys.stdout)
        #handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger

def logger_style_artist(func):
    def wrapper(*args, **kwargs):
        global _priv_attr
        # do not colorize output when logging to a file
        return func(*args, **kwargs) if _priv_attr.colorize else args[0]
    return wrapper

class CSCCursesMenu(object):

    DEFAULT_CREDENTIALS_FILE_NAME = 'csccredentials.json'

    def __init__(self, config_file_name):
        self.running = True
        os.system('clear')
        self.screen = curses.initscr()
        self.screen.keypad(1) #enable keyboard numpad

        #init curses and curses input
        curses.noecho() #disable the keypress echo to prevent double input
        curses.cbreak() #disable line buffers to run the keypress immediately
        curses.start_color()
        curses.curs_set(0) #hide cursor

        #set up color pair
        curses.init_pair(1, curses.COLOR_BLUE,  curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_RED,   curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(4, 33,                 curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_RED,   curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN,  curses.COLOR_BLACK)

        self.hilite_color     = curses.color_pair(1)
        self.title_color      = curses.color_pair(2)
        self.status_bar_color = curses.color_pair(3)
        self.blue_color       = curses.color_pair(4)
        self.red_color        = curses.color_pair(5)
        self.cyan_color       = curses.color_pair(6)
        self.normal_color     = curses.A_NORMAL

        self.menu = {
            'environment': {
                'subtitle': 'Choose an environment'
                #parent: exit
            },
            'virtual_host': {
                'subtitle': 'Choose a virtual host',
                'parent': 'environment'
            },
            'users': {
                'subtitle': 'Choose a user',
                'parent': 'virtual_host'
            },
            'cache': {
                'subtitle': None
                #parent: exit
            }
        }
        self._load_environment_menu()

        signal.signal(signal.SIGINT, self._sig_handler)

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_file_path = f'{self.script_dir}/{config_file_name}'
        try:
            f = open(self.config_file_path, 'r')
        except:
            self.conf_file = False
            self.users_data = {}
        else:
            self.conf_file = True
            with f:
                self.users_data = json.load(f)

    def _sig_handler(self, signal, frame):
        self.destroy()
        print(CSC.highlight('CSC tester terminated', 'DeepPink1', bold=True), file=sys.stderr)
        sys.exit(1)

    def _prompt_selection(self, parent=None):
        sub_menu = self.menu['selected']
        if not parent:
            if 'parent' in self.menu[sub_menu]:
                back_option = f'Return to previous menu ({self.menu[sub_menu]["parent"].title()})'
            else:
                back_option = None
        else:
            back_option = f'Return to previous menu ({parent["title"]})'

        exit_option = "Exit"

        option_count = len(self.menu[sub_menu]['options'])
        list_count = option_count + (0 if not back_option else 1) #considering back option

        input_key = None

        #keys mapping
        back_keys  = [curses.KEY_LEFT, ord('B'), ord('b')]
        down_keys  = [curses.KEY_DOWN, ord('J'), ord('j')]
        enter_keys = [curses.KEY_RIGHT, ord('\n')]
        exit_keys  = [ord('Q'), ord('q')]
        help_keys  = [ord('H'), ord('h')]
        up_keys    = [curses.KEY_UP, ord('K'), ord('k')]

        self.selected_option = 0
        while input_key not in enter_keys:
            #self.screen.clear()
            self.screen.erase()
            self.screen.border(0)
            self._draw_title()
            self._draw_status_bar("Press 'h' for help")
            list(map(lambda o: self._draw_option(o, self.hilite_color if self.selected_option == o else self.normal_color), range(option_count)))

            self.screen.addstr(self.curr_ord + option_count + 1, 4, f'{exit_option if not back_option else back_option}', self.hilite_color if self.selected_option == option_count else self.normal_color)

            if back_option is not None:
                color = self.hilite_color if self.selected_option == option_count + 1 else self.normal_color
                self.screen.addstr(self.curr_ord + option_count + 2, 4, f'{exit_option}', color)

            self.screen.refresh()

            input_key = self.screen.getch()

            if input_key in down_keys:
                if self.selected_option < list_count:
                    self.selected_option += 1
                else:
                    self.selected_option = 0

            if input_key in up_keys:
                if self.selected_option > 0:
                    self.selected_option -= 1
                else:
                    self.selected_option = list_count

            if input_key in back_keys and back_option is not None:
                self.selected_option = list_count - 1 #auto select back and return
                break

            if input_key in help_keys:
                self._help_scr()

            if input_key in exit_keys:
                self.selected_option = list_count #auto select exit and return
                break

        return self.selected_option

    def _draw_option(self, option_number, style):
        sub_menu = self.menu['selected']
        self.screen.addstr(self.curr_ord + option_number,
                           4,
                           f'{self.menu[sub_menu]["options"][option_number]["title"]}',
                           style)

    def _draw_title(self, subtitle=None):
        self.screen.attron(curses.A_UNDERLINE)
        self.screen.attron(curses.A_BOLD)
        self.screen.attron(self.title_color)
        if not self._draw_title_enhanched():
            self.screen.addstr(2, 2, 'CSC Tester')
            self.curr_ord = 4
        self.screen.attroff(curses.A_UNDERLINE)
        self.screen.attroff(curses.A_BOLD)
        self.screen.attroff(self.title_color)
        if subtitle is None:
            sub_menu = self.menu['selected']
            if 'subtitle' in self.menu[sub_menu]:
                if isinstance(self.menu[sub_menu]['subtitle'], list):
                    subtitle = self.menu[sub_menu]['subtitle']
                elif isinstance(self.menu[sub_menu]['subtitle'], dict):
                    subtitle = [ self.menu[sub_menu]['subtitle'] ]
                elif isinstance(self.menu[sub_menu]['subtitle'], str):
                    subtitle = [{
                        'text': self.menu[sub_menu]['subtitle'],
                        'style': [ curses.A_BOLD ]
                    }]
                else:
                    return
            else:
                return
        elif isinstance(subtitle, dict):
            subtitle = [ subtitle ]
        elif isinstance(subtitle, str):
            subtitle = [{
                'text': subtitle,
                'style': [ curses.A_BOLD ]
            }]
        else:
            return

        for row in subtitle:
            list(map(lambda x: self.screen.attron(x), row['style'] if 'style' in row else []))
            self.screen.addstr(self.curr_ord, 2, row['text'])
            list(map(lambda x: self.screen.attroff(x), row['style'] if 'style' in row else []))
            self.curr_ord += 1 if len(subtitle) > 1 else 0
        self.curr_ord += 1

    def _draw_title_enhanched(self):
        max_y, max_x = self.screen.getmaxyx()
        left_indent = 3
        if max_x < 43 + left_indent + 1:
            return False
        self.screen.attroff(curses.A_UNDERLINE)
        self.screen.addstr(1, left_indent, '                 _            _            ')
        self.screen.addstr(2, left_indent, '                | |          | |           ')
        self.screen.addstr(3, left_indent, '  ___ ___  ___  | |_ ___  ___| |_ ___ _ __ ')
        self.screen.addstr(4, left_indent, ' / __/ __|/ __| | __/ _ \/ __| __/ _ \ \'__|')
        self.screen.addstr(5, left_indent, '| (__\__ \ (__  | ||  __/\__ \ ||  __/ |   ')
        self.screen.addstr(6, left_indent, ' \___|___/\___|  \__\___||___/\__\___|_|   ')
        self.curr_ord = 8
        return True

    def _load_environment_menu(self):
        self.menu['selected'] = 'environment'
        sub_menu = self.menu['environment']
        sub_menu['options'] = [ { 'title': e.title(), 'value': e } for e in CSC.env_IDs ]
        self.environment_name = None
        self.v_host_ctx_path  = None

    def _load_virtual_host_menu(self):
        self.menu['selected'] = 'virtual_host'
        sub_menu = self.menu['virtual_host']
        sub_menu['options'] = [ { 'title': v.title(), 'value': v } for v in CSC.virtual_host if self.environment_name in CSC.virtual_host[v] ]
        self.v_host_ctx_path = None

    def _load_users_menu(self):
        self.menu['selected'] = 'users'
        sub_menu = self.menu['users']
        sub_menu['options'] = []
        self.curr_users = {}
        for u in self.users_data:
            env_allowed_list = self.users_data[u]['environment']
            for e in env_allowed_list:
                if 'name' in e and self.environment_name in e['name']:
                    self.curr_users[u] = e['password'] if 'password' in e else 'password'
                    sub_menu['options'].append({
                        'title': u,
                        'value': u
                    })
                    break
        sub_menu['options'] = sorted(sub_menu['options'], key=itemgetter('title'))
        sub_menu['options'].append({
            'title': 'Existing Session-Key',
            'value': 'sessionkey'
        })
        sub_menu['options'].append({
            'title': 'Create a user',
            'value': 'new'
        })

    def _user_cache_management(self):
        if 'cache' not in self.users_data:
            return False
        self.menu['selected'] = 'cache'
        cache = self.users_data['cache']
        sub_menu = self.menu['cache']
        sub_menu['options'] = [
            {
                'title': 'yes',
                'value': 'y'
            },
            {
                'title': 'no',
                'value': 'n'
            }
        ]
        sub_menu['subtitle'] = [
            {
                'text': 'Use last configuration?',
                'style': [ curses.A_BOLD ]
            },{
                'text': f'{cache["username"]} \u2192  {[ k for k, v in CSC.env_URLs.items() if v == cache["ctx_path"] ][0]}',
                'style': [
                    curses.A_BOLD,
                    self.blue_color
                ]
            }
        ]
        selected_option = self._prompt_selection()
        if selected_option is len(sub_menu['options']):
            return None
        use_cache = sub_menu['options'][selected_option]['value'] == 'y'
        if use_cache:
            self.environment_name = cache['environment']
            self.v_host_ctx_path  = cache['ctx_path']
            self.username = cache['username']
            self.password = cache['password']
        return use_cache

    def _help_scr(self):
        self.screen.clear()
        self.screen.border(0)
        _, max_x = self.screen.getmaxyx()
        self.screen.attron(curses.A_BOLD)
        self.screen.attron(self.red_color)
        self.screen.addstr(1, 2, 'CSC Tester ' + __version__ + ' - 2018 ' + __author__)
        self.screen.attroff(self.red_color)
        self.screen.attron(self.cyan_color)
        self.screen.addstr(4, 2, '{:>18}'.format('J j DOWN_ARROW:'))
        self.screen.addstr(5, 2, '{:>18}'.format('K k UP_ARROW:'))
        self.screen.addstr(6, 2, '{:>18}'.format('ENTER RIGHT_ARROW:'))
        self.screen.addstr(7, 2, '{:>18}'.format('B b LEFT_ARROW:'))
        self.screen.addstr(8, 2, '{:>18}'.format('Q q:'))
        self.screen.addstr(9, 2, '{:>18}'.format('H h:'))
        self.screen.attroff(self.cyan_color)
        self.screen.addstr(4, 21, 'down')
        self.screen.addstr(5, 21, 'up')
        self.screen.addstr(6, 21, 'select option')
        self.screen.addstr(7, 21, 'back')
        self.screen.addstr(8, 21, 'quit')
        self.screen.addstr(9, 21, 'display help')
        self.screen.attroff(curses.A_BOLD)
        self._draw_status_bar('press any key to go back')
        self.screen.getch()


    def display(self):
        self.username = self.password = session_key = None
        use_cache = self._user_cache_management()
        if use_cache is None:
            self.destroy()
            return None
        while not use_cache:
            if not self.environment_name:
                #environment
                self._load_environment_menu()
                sub_menu = self.menu['environment']
                selected_option = self._prompt_selection()
                if selected_option is len(sub_menu['options']):
                    self.destroy()
                    return None
                env = sub_menu['options'][selected_option]
                self.environment_name = env['value']
            elif not self.v_host_ctx_path:
                #virtual host
                self._load_virtual_host_menu()
                sub_menu = self.menu['virtual_host']
                selected_option = self._prompt_selection()
                if selected_option is len(sub_menu['options']):
                    #back
                    self.environment_name = None
                    continue
                elif selected_option is len(sub_menu['options']) + 1:
                    self.destroy()
                    return None
                v_host = sub_menu['options'][selected_option]
                self.v_host_ctx_path = CSC.virtual_host[v_host['value']][self.environment_name]
            else:
                #user
                sub_menu = self.menu['users']
                self._load_users_menu()
                selected_option = self._prompt_selection()
                if selected_option is len(sub_menu['options']):
                    #back
                    self.v_host_ctx_path = None
                    continue
                elif selected_option is len(sub_menu['options']) + 1:
                    self.destroy()
                    return None
                elif sub_menu['options'][selected_option]['value'] == 'sessionkey':
                    session_key = self._get_string('Session Key:')
                    if not session_key:
                        continue
                    break
                elif sub_menu['options'][selected_option]['value'] == 'new':
                    while True:
                        username = self._get_string('Username:')
                        if not username:
                            break
                        password = self._get_string('Password:')
                        if password:
                            break
                    if not username or not password:
                        username = password = None
                        continue
                    elif self._create_user(username, password):
                        break
                    continue
                self.username = sub_menu['options'][selected_option]['value']
                if self.username is not None:
                    self.password = self.curr_users[self.username]
                #TODO no user available
                break
        self.destroy()
        ret = {
            'environment': self.environment_name,
            'ctx_path': self.v_host_ctx_path,
            'username': self.username,
            'password': self.password
        }
        if self.username and not use_cache:
            #save last data used
            self.users_data['cache'] = ret
            self._update_config_file()
        ret['session_key'] = session_key
        return ret

    def _create_user(self, username, password):
        self.username = username
        self.password = password
        if username == 'cache':
            #TODO invalid username 'cache'
            return False
        if username not in self.users_data:
            self.users_data[username] = {
                'environment': [{
                    'name': [
                        self.environment_name
                    ],
                    'password': password
                }]
            }
        else:
            user = self.users_data[username]
            if 'environment' not in user:
                user['environment'] = []
            for e in user['environment']:
                if 'name' in e and self.environment_name in e['name']:
                    #clean old declarations
                    if 'password' in e and password != e['password']:
                        e['name'].remove(self.environment_name)
                    elif 'password' not in e and password != 'password':
                        e['name'].remove(self.environment_name)
                    else:
                        #configuration already present
                        return True
                    if len(e['name']) is 0:
                        user['environment'].remove(e)
            for e in user['environment']:
                if 'password' in e and password == e['password'] or 'password' not in e and password == 'password':
                    if 'name' not in e:
                        e['name'] = []
                    if self.environment_name not in e['name']:
                        e['name'].append(self.environment_name)
                    return True
            user['environment'].append({
                'name': [
                    self.environment_name
                ],
                'password': password
            })
        return True

    def _update_config_file(self, content=None):
        if content is None:
            content = self.users_data

        if self.conf_file:
            tmp_backup_file = f'{tempfile.gettempdir()}/{next(tempfile._get_candidate_names())}'
            try:
                shutil.copy(self.config_file_path, tmp_backup_file)
            except Exception as e:
                print('{} {}'.format(CSC.highlight('An error occurred while creating a backup file', 'red', bold=True), e), file=sys.stderr)
                return False
        try:
            open(self.config_file_path, 'w').close()
            with open(self.config_file_path, 'w') as f:
                f.write(json.dumps(content, indent=4, sort_keys=True))
        except Exception as e:
            print('{} {}'.format(CSC.highlight('An error occurred while updating your configuration file', 'yellow'), e), file=sys.stderr)
            if self.conf_file:
                try:
                    print(CSC.highlight('Restoring the old configuration', 'yellow'), file=sys.stderr)
                    shutil.copy(tmp_backup_file, self.config_file_path)
                except:
                    print(CSC.highlight('Cannot restore configuration file, a backup file has been saved in path ' + tmp_backup_file, 'red', bold=True), file=sys.stderr)
                    return False
                os.remove(tmp_backup_file)
            return False
        if self.conf_file:
            os.remove(tmp_backup_file)
        return True

    def _draw_status_bar(self, message):
        max_y, max_x = self.screen.getmaxyx()
        if len(message) > max_x - 2:
            return False
        self.screen.addstr(max_y - 2, 1, f'{message: >{str(max_x - 3)}} ', self.status_bar_color)
        return True

    def _get_string(self, label, draw_title=True):
        self.screen.clear()
        if draw_title:
            self._draw_title('')
        curses.echo()
        curses.curs_set(1)
        _, max_x = self.screen.getmaxyx()
        self.screen.border(0)
        indent = max_x//5 - len(label) if max_x//5 - len(label) > 0 else 2
        curr_ord = self.curr_ord + 2
        self.screen.addstr(curr_ord, indent, label, curses.A_BOLD)
        self._draw_status_bar('Insert an empty string to go back')
        self.screen.refresh()
        try:
            textpad.rectangle(self.screen, curr_ord - 1, indent + len(label) + 1, curr_ord + 1 , max_x - 2) #rectangle(win, uly, ulx, lry, lrx)
            val = self.screen.getstr(curr_ord, indent + len(label) + 2, max_x - len(label) - indent - 4) #getstr(begin_y, begin_x, ncols)
            return val.decode('utf-8').strip()
        except:
            return None
        finally:
            curses.noecho()
            curses.curs_set(0)

    def destroy(self):
        self.running = False
        curses.endwin()


class CSC(object):

    ALGO_RSA_ENC             = '1.2.840.113549.1.1.1'
    ALGO_SHA1_WITH_RSA_ENC   = '1.2.840.113549.1.1.5'
    ALGO_SHA224_WITH_RSA_ENC = '1.2.840.113549.1.1.14'
    ALGO_SHA256_WITH_RSA_ENC = '1.2.840.113549.1.1.11'
    ALGO_SHA384_WITH_RSA_ENC = '1.2.840.113549.1.1.12'
    ALGO_SHA512_WITH_RSA_ENC = '1.2.840.113549.1.1.13'
    ALGO_RSASSA_PSS          = '1.2.840.113549.1.1.10'

    HASH_SHA1_OID   = '1.3.14.3.2.26'
    HASH_SHA224_OID = '2.16.840.1.101.3.4.2.4'
    HASH_SHA256_OID = '2.16.840.1.101.3.4.2.1'
    HASH_SHA384_OID = '2.16.840.1.101.3.4.2.2'
    HASH_SHA512_OID = '2.16.840.1.101.3.4.2.3'

    HASH_SHA1_VALUE       = 'A8/XQ2YfB5dfovEiDFGUy6/0hFE=' #echo abc | sha1sum | xxd -r -p | base64 | tr -d '\r\n'
    HASH_SHA224_VALUE     = '9ck7bwb3xW1+pyDBIeOx+2cw5c9fGNd2vw8tiA==' #echo abc | sha224sum | xxd -r -p | base64 | tr -d '\r\n'
    HASH_SHA256_VALUE     = '7eqv8/F3StKIhnN3DG1kCX45G8Ni19b7NJgt3w79GMs=' #echo abc | sha256sum | xxd -r -p | base64 | tr -d '\r\n'
    HASH_SHA384_VALUE     = '6NFCC0/0HD8SGG2JSpnhxKpoHaecRwB+na3s2eywSC7h4iRRDnSEB4wCifNDlrnD' #echo abc | sha384sum | xxd -r -p | base64 | tr -d '\r\n'
    HASH_SHA512_VALUE     = 'TyhdDAzHcobYcxeYt6riY54oJw1BZvQNdpy73KUjBxTYSEg9Nk4vOf5suQg8FSKbOaM2FevG1XYF98Q/aQZznQ==' #echo abc | sha512sum | xxd -r -p | base64 | tr -d '\r\n'

    env_IDs = [
        'produzione'
    ]

    virtual_host = OrderedDict([
        ('time4mind', {
            'produzione': 'https://services.time4mind.com/csc/v0'
        }),
        ('bankid-no', {
            'produzione': 'https://bnkidno.time4mind.com/csc/v0'
        }),
        ('bankid-se', {
            'produzione': 'https://bnkidse.time4mind.com/csc/v0'
        }),
        ('ftn', {
            'produzione': 'https://ftn.time4mind.com/csc/v0'
        }),
        ('globalsign', {
            'produzione': 'https://globalsign.time4mind.com/csc/v0'
        }),
        ('idin', {
            'produzione': 'https://idin.time4mind.com/csc/v0'
        }),
        ('nemid', {
            'produzione': 'https://nemid.time4mind.com/csc/v0'
        }),
        ('transsped', {
            'transsped (produzione)': 'https://services.cloudsignature.online/csc/v0'
        })
    ])

    env_URLs = {
        'produzione':       'https://services.time4mind.com/csc/v0'
    }

    service_logo_URLs = OrderedDict([
        ('adobe-prod',         'https://services.time4mind.com/res_ext/vendors/adobe/csc_adobe.jpg'),
        ('bankidse-prod',      'https://services.time4mind.com/res_ext/vendors/bankid/csc_bankid.jpg'),
        ('bankidno-prod',      'https://services.time4mind.com/res_ext/vendors/bankidno/csc_bankidno.jpg'),
        ('ftn-prod',           'https://services.time4mind.com/res_ext/vendors/ftn/logo-en.png'),
        ('globalsign-prod',    'https://services.time4mind.com/res_ext/vendors/globalsign/csc_globalsign.png'),
        ('idin-prod',          'https://services.time4mind.com/res_ext/vendors/idin/idin_logo.png'),
        ('intesi-prod-new',    'https://services.time4mind.com/res_ext/logo_IG_symbol.png'),
        ('nemid-prod',         'https://services.time4mind.com/res_ext/vendors/nemid/csc_nemid.jpg'),
        ('transsped-prod-new', 'https://services.time4mind.com/res_ext/vendors/transsped/csc_transsped.png')
    ])

    oauth_logo_URLs = OrderedDict([
        ('bankidse-prod',      'https://services.time4mind.com/res_ext/vendors/bankid/img/oauthLogo.png'),
        ('bankidno-prod',      'https://services.time4mind.com/res_ext/vendors/bankidno/img/oauthLogo.png'),
        ('globalsign-prod',    'https://services.time4mind.com/res_ext/vendors/globalsign/img/oauthLogo.png'),
        ('idin-prod',          'https://services.time4mind.com/res_ext/vendors/idin/img/oauthLogo.png'),
        ('intesi-prod',        'https://services.time4mind.com/res_ext/faviconX180.png'), #XXX ???
        ('nemid-prod',         'https://services.time4mind.com/res_ext/vendors/nemid/img/oauthLogo.png'),
        ('transsped-prod-new', 'https://services.time4mind.com/res_ext/vendors/transsped/img/oauthLogo.png'),
    ])

    @staticmethod
    def getinfostr():
        return '{}\n{}\n{}\n{}\n{}\n{}\n\n\n'.format('                 _            _            ',
                                                     '                | |          | |           ',
                                                     '  ___ ___  ___  | |_ ___  ___| |_ ___ _ __ ',
                                                     ' / __/ __|/ __| | __/ _ \/ __| __/ _ \ \'__|',
                                                     '| (__\__ \ (__  | ||  __/\__ \ ||  __/ |   ',
                                                     ' \___|___/\___|  \__\___||___/\__\___|_|   ') \
        + f'{CSC.highlight("Version:", bold=True)} {__version__}\n' \
        + f'{CSC.highlight("Author:", bold=True)} {__author__}'

    def _generic_test(self, cfg):
        tests = cfg['tests']
        response = []
        for i in range(0, len(tests), 1):
            t = tests[i]
            h = {} if 'headers' not in t else t['headers']
            h['Content-Type'] = 'application/json'
            if 'input' not in t or t['input'] is None:
                r = requests.get(self.service_URLs[cfg['service']], headers=h, verify=False, json=t['input'])
            else:
                r = requests.post(self.service_URLs[cfg['service']], headers=h, verify=False, json=t['input'])
            if r.text is None or str(r.text) == '':
                j = {}
            else:
                try:
                    j = r.json()
                except ValueError:
                    self.logger.error(f'[ {CSC.highlight("KO", "red", bold=True)} ] {cfg["service"]} {t["name"] if "name" in t else "test " + str(i + 1)}: cannot parse json response')
                    return [] #TODO should not return??
            check = t['exp_result']

            def _traverse_json(root, path):
                if not isinstance(root, dict) or not isinstance(path, str):
                    return None
                if '>' in path:
                    for k in path.split('>'):
                        if k in root:
                            root = root[k]
                        else:
                            return None
                    return root
                return root[path] if path in root else None

            def _in_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for a in c['arg']:
                    if not _traverse_json(j, a):
                        return True
                return False

            def _not_in_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for a in c['arg']:
                    if _traverse_json(j, a) is not None:
                        return True
                return False

            def _equal_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    pattern = c['arg'][key]
                    node = _traverse_json(j, key)
                    if not node:
                        return True
                    if isinstance(pattern, list):
                        if not isinstance(node, list) or len([ x for x in zip(pattern, node) if x[0] != x[1] ]) > 0:
                            return True
                    elif not re.match(pattern, node):
                        return True
                return False

            def _not_equal_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if key in j and j[key] == c['arg'][key]:
                        return True
                return False

            def _len_lesser_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    node = _traverse_json(j, key)
                    if not isinstance(node, list) or len(node) >= c['arg'][key]:
                        return True
                return False

            def _len_eq_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    node = _traverse_json(j, key)
                    if not isinstance(node, list) or len(node) != c['arg'][key]:
                        return True
                return False

            def _len_greater_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    node = _traverse_json(j, key)
                    if not isinstance(node, list) or len(node) <= c['arg'][key]:
                        return True
                return False

            for c in check:
                try:
                    if {
                        'in':     _in_callback,
                        'not in': _not_in_callback,
                        'eq':     _equal_callback,
                        'not eq': _not_equal_callback,
                        '<':      _len_lesser_callback,
                        '=':      _len_eq_callback,
                        '>':      _len_greater_callback
                    }[c['condition']]():
                        self._print_KO_msg(cfg['service'], i + 1, t['input'], j, t['name'] if 'name' in t else None, error_level=2 if 'err_level' not in t else t['err_level'])
                        self.logger.error(f'{CSC.highlight(" Expected result rules:", bold=True)} {CSC.highlight(json.dumps(check, indent=4, sort_keys=True), "IndianRed1")}\n\n')
                        break
                except Exception as e:
                    self.logger.error(f'{CSC.highlight("Invalid condition check: " + c["condition"], "yellow", bold=True)} - {type(e).__name__} {e}')
                    traceback.print_exc()
            else:
                self._print_OK_msg(cfg['service'], i + 1, t['name'] if 'name' in t else None)

            response.append(j)
        return response

    def info_test(self):
        r = requests.get(self.service_URLs['info'], verify=False)
        j = r.json()
        self.logger.info(f'{json.dumps(j, indent=4, sort_keys=True)}')
        if 'logo' in j:
            #check logo existence
            rr = requests.get(j['logo'], allow_redirects=False)
            if rr is None:
                self.logger.error(f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test failed: {CSC.highlight("info response is empty", color="yellow")}')
            elif rr.status_code != 200:
                self.logger.error(f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test failed: {CSC.highlight("status_code " + str(rr.status_code), color="yellow")}')
            elif rr.headers['Content-Type'] != 'image/png' and rr.headers['Content-Type'] != 'image/jpeg':
                self.logger.error(f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test failed: {CSC.highlight("content type " + str(rr.headers["Content-Type"]), color="yellow")}')
            else:
                self.logger.info(f'[ {CSC.highlight("OK", color="green", bold=True)} ] Logo test')
        else:
            self.logger.error(CSC.highlight('Logo URL not present', color='yellow', bold=True))
        cfg = {
            'service': 'info',
            'tests': [
                {
                    'name': 'no arguments',
                    'input': None,
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'lang': 'en-US' }, }
                    ]
                },
                {
                    'name': 'IT language',
                    'input': { 'lang': 'it-IT' },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'lang': 'it-IT' }, }
                    ]
                }
            ]
        }
        self._generic_test(cfg)

    def login_test(self):
        if self.session_key is not None:
            self.logger.info(f'{CSC.highlight("Login disabled. Using configured sessionkey:", bold=True)} {self.session_key}')
            return
        if self.credential_encoded is None:
            self._set_error_level(1)
            raise RuntimeError('*** Login credential unavailable ***')
        cfg = {
            'service': 'auth/login',
            'tests': [
                { #1
                    'name': 'simple login',
                    'headers': { 'Authorization' : 'Basic ' + self.credential_encoded },
                    'input': None,
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'access_token' ] },
                        { 'condition': 'not in', 'arg': [ 'refresh_token', 'error' ] }
                    ]
                },
                { #2
                    'name': 'remember me login',
                    'headers': { 'Authorization' : 'Basic ' + self.credential_encoded },
                    'input': { 'rememberMe': True },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'access_token', 'refresh_token' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }
        r = self._generic_test(cfg)
        self.session_key = None
        self.refresh_token = None
        found = False
        #save access_token/refresh_token and revoke the others
        for i in range(len(cfg['tests']) - 1, -1, -1):
            if not found and 'error' not in r[i] and 'access_token' in r[i]:
                self.session_key = r[i]['access_token']
                if 'refresh_token' in r[i]:
                    self.refresh_token = r[i]['refresh_token']
                found = True
            elif 'access_token' in r[i]:
                self.single_revoke(r[i]['access_token'])
        if self.session_key is None:
            self._set_error_level(1)
            raise RuntimeError('*** Session key unavailable ***')
        return self.session_key, self.refresh_token

    def list_test(self):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        cfg = {
            'service': 'credentials/list',
            'tests': [
                { #1
                    'name': 'maxResults 1',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'maxResults': 1 },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'credentialIDs' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': '<', 'arg': { 'credentialIDs': 2 } }
                    ]
                },
                { #2
                    'name': 'maxResults 5',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'maxResults': 5 },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'credentialIDs' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': '<', 'arg': { 'credentialIDs': 6 } }
                    ]
                },
                { #3
                    'name': 'maxResults 20',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'maxResults': 20 },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'credentialIDs' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': '<', 'arg': { 'credentialIDs': 21 } }
                    ]
                }
            ]
        }
        r = self._generic_test(cfg)
        self.credential_IDs = self.list_utility(64)
        if len(self.credential_IDs) > 1:
            chunk_size = len(self.credential_IDs)//5 + 1
            if len(self.list_utility(chunk_size, 5)) == len(self.credential_IDs):
                self.logger.info(f'[ {CSC.highlight("OK", "green", bold=True)} ] credentials/list - pagination test')
            else:
                self.logger.error(f'[ {CSC.highlight("KO", "red", bold=True)} ] credentials/list - pagination test')
        return self.credential_IDs

    def list_utility(self, max_results=1, iterations=-1):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        credentials_ids = []
        payload = { 'maxResults': max_results }
        dots_num = 0
        while iterations != 0:
            r = requests.post(self.service_URLs['credentials/list'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
            if r.text is not None and str(r.text) != '':
                try:
                    j = r.json()
                except ValueError:
                    self.logger.error(CSC.highlight('Invalid json response while iterating credentials list', 'red', bold=True))
                    break
            else:
                self.logger.error(CSC.highlight('Invalid response while iterating credentials list', 'red', bold=True))
                break
            if 'error' in j:
                break
            elif 'credentialIDs' in j and isinstance(j['credentialIDs'], list):
                credentials_ids.extend(j['credentialIDs'])
            if 'nextPageToken' not in j:
                break
            payload['pageToken'] = j['nextPageToken']
            iterations = iterations if iterations < 0 else iterations - 1
            sys.stdout.write("\r\033[K" if dots_num is 5 else ". ")
            dots_num = (dots_num + 1)%6
            sys.stdout.flush()
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        return credentials_ids

    def credentials_info_test(self, credential_id=None, auth_mode='explicit'):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')

        cfg = {
            'service': 'credentials/info',
            'tests': [
                { #1
                    'name': 'credential_id only',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #2
                    'name': 'certificates none',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'none' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'cert>certificates', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN', 'PIN', 'OTP' ] },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #3
                    'name': 'certificates single',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN', 'PIN', 'OTP' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #4
                    'name': 'certificates chain',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'chain' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'PIN', 'OTP' ] },
                        { 'condition': '>', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #5
                    'name': 'certInfo',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single', 'certInfo': True },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #6
                    'name': 'no certInfo',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                },
                { #7
                    'name': 'authInfo',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'chain', 'authInfo': True },
                    'exp_result': [
                        { 'condition': 'in' if auth_mode == 'explicit' else 'not in', 'arg': [ 'PIN', 'OTP' ] },
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo' ] },
                        { 'condition': '>', 'arg': { 'cert>certificates': 1 } },
                        { 'condition': 'eq', 'arg': { 'key>algo': [ "1.2.840.113549.1.1.1", "1.2.840.113549.1.1.5", "1.2.840.113549.1.1.14", "1.2.840.113549.1.1.11", "1.2.840.113549.1.1.12", "1.2.840.113549.1.1.13", "1.2.840.113549.1.1.10" ] } }
                    ]
                }
            ]
        }
        self._generic_test(cfg)

    def get_credential_info(self, credential_id=None, print_details=False, certificates='none'):
        if credential_id is None:
            raise RuntimeError('*** Credential ID unavailable ***')
        if self.session_key is None:
            self.session_key = self._get_session_key()

        payload = {
            'certificates': certificates,
            'authInfo': True,
            'certInfo': True,
            'credentialID': credential_id
        }
        r = requests.post(self.service_URLs['credentials/info'], headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, verify=False, json=payload)
        j = r.json()
        if 'error' in j:
            self._set_error_level(1 if 'Session is invalid' else 3)
            raise RuntimeError(f'*** Unable to get credential info {"" if "error_description" not in j else (": " + j["error_description"])} ***')
        is_valid = otp_presence = pin_presence = False
        otp_type = auth_mode = None
        pin_presence = 'PIN' in j and 'presence' in j['PIN'] and j['PIN']['presence'] == 'true'
        if 'OTP' in j:
            otp_presence = 'presence' in j['OTP'] and j['OTP']['presence'] == 'true'
            if 'type' in j['OTP']:
                otp_type = j['OTP']['type']
        if 'authMode' in j:
            auth_mode = j['authMode']
        is_valid =  'cert' in j and 'status' in j['cert'] and j['cert']['status'] == 'valid' and 'key' in j and 'status' in j['key'] and j['key']['status'] == 'enabled'

        key_algo = None
        if 'key' in j and 'algo' in j['key']:
            key_algo = j['key']['algo']

        if print_details:
            self.logger.debug(f'{CSC.highlight("Credential ID", bold=True)} {CSC.highlight(credential_id, "SeaGreen2" if is_valid else "red", bold=True)}')
            self.logger.debug(json.dumps(j, indent=4, sort_keys=True))

        return is_valid, auth_mode, pin_presence, otp_presence, otp_type, key_algo

    def send_otp_test(self, credential_id=None):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if credential_id is None:
            raise RuntimeError('*** Credential ID unavailable ***')
        cfg = {
            'name': 'default',
            'service': 'credentials/sendOTP',
            'tests': [
                { #1
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description' ] }
                    ]
                }
            ]
        }
        r = self._generic_test(cfg)
        for rr in r:
            if 'error' not in rr:
                self.logger.debug(CSC.highlight(f'* OTP for credential {credential_id} sent', 'DeepSkyBlue2'))
                break

    def send_otp(self, credential_id):
        try:
            cert_status, auth_mode, pin_presence, otp_presence, otp_type, key_algo = self.get_credential_info(credential_id)
            if auth_mode != 'implicit' and otp_presence and otp_type == 'online':
                payload = {
                    'credentialID': credential_id
                }
                r = requests.post(self.service_URLs['credentials/sendOTP'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
                if r.text != '' and 'error' in r.json():
                    self._set_error_level(3)
                    j = r.json()
                    self.logger.error(f'{CSC.highlight("An error occurred while sending an OTP for credential {credential_id}", "red", bold=True)} - {j}')
        except Exception as e:
            self._set_error_level(3)
            self.logger.error(f'{CSC.highlight("An error occurred while sending an OTP for credential {credential_id}", "red", bold=True)} - {type(e).__name__} {e}')
        self.single_revoke(noout=True)


    def authorize_test(self, credential_id=None, auth_mode='explicit', pin_presence=True, otp_presence=True, otp_type='online', num_signatures=20, is_valid=True):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if auth_mode in [ 'oauth2code', 'oauth2token' ]:
            self.SAD = None
            self.logger.warn(CSC.highlight(f'Unable to perform authorizations test: invalid authMode \u2192  {auth_mode}', 'yellow', bold=True))
            return
        pin = None
        if auth_mode == 'explicit' and pin_presence:
            if self.DEFAULT_PIN is None:
                pin = getpass.getpass(CSC.highlight('Please enter the PIN value [press ENTER to abort]: ', bold=True))
                if pin == '':
                    raise RuntimeError('*** Unable to perform Authorize tests: PIN is empty ***')
            elif self.quiet:
                pin = self.DEFAULT_PIN
            else:
                tmp = getpass.getpass(CSC.highlight('Confirm or change the default PIN [' + self.DEFAULT_PIN + ']: ', bold=True))
                pin = tmp if tmp != '' else self.DEFAULT_PIN

        if auth_mode == 'explicit' and otp_presence:
            if self.quiet:
                raise RuntimeError('*** Unable to perform Authorize tests in quiet mode: OTP is required ***')
            otp = input(CSC.highlight('Please enter the OTP value [press ENTER to abort]: ', bold=True))
            if otp == '':
                raise RuntimeError('*** Unable to perform Authorize tests: OTP is empty ***')

        # TODO fix this
        if is_valid:
            wrong_pin_test_error = 'invalid_pin'
            wrong_pin_test_error_description = 'The PIN is invalid'
        else:
            wrong_pin_test_error = 'invalid_request'
            wrong_pin_test_error_description = 'Invalid certificate status'

        cfg = {
            'service': 'credentials/authorize',
            'tests': [
                { #2 - wrong PIN
                    'name': 'wrong PIN',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': '>>0',
                        'OTP': None
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'error': wrong_pin_test_error, 'error_description': wrong_pin_test_error_description } },
                    ]
                },
                { #3
                    'name': f'valid authorize request for {num_signatures} signatures',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'err_level': 3,
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': None,
                        'OTP': None
                    },
                    'exp_result': [
                        { 'condition': 'in' if is_valid else 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'not in' if is_valid else 'in', 'arg': [ 'error' ] }
                    ]
                },
                { #4
                    'name': 'invalid PIN format',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': 12345678,
                        'OTP': None
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'error': 'invalid_request', 'error_description': 'Invalid parameter PIN' } },
                    ]
                },
                { #5
                    'name': 'invalid OTP format',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': None,
                        'OTP': 12345678
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'error': 'invalid_request', 'error_description': 'Invalid parameter OTP' } },
                    ]
                }
            ]
        }

        if auth_mode == 'explicit':
            if otp_presence:
                for i in cfg['tests']:
                    if 'OTP' in i['input'] and i['input']['OTP'] is None:
                        i['input']['OTP'] = otp
                tmp = { #1 - wrong OTP
                    'name': 'wrong OTP',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'OTP': '>>0',
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': None
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'eq', 'arg': { 'error': 'invalid_otp' if is_valid else 'invalid_request', 'error_description': 'The OTP is invalid' if is_valid else 'Invalid certificate status' } }
                    ]
                }
                cfg['tests'].insert(0, tmp)
            else:
                for i in cfg['tests']:
                    if 'OTP' in i['input'] and i['input']['OTP'] is None:
                        i['input'].pop('OTP', None)

        if auth_mode == 'explicit' and pin_presence:
            for i in cfg['tests']:
                if 'PIN' in i['input'] and i['input']['PIN'] is None:
                    i['input']['PIN'] = pin

        self.SAD = None
        try:
            r = self._generic_test(cfg)
        except KeyboardInterrupt:
            self.logger.warn(CSC.highlight('Authorization tests interrupted...skipping to next credential', 'yellow'))
            return None
        for i in range(len(cfg['tests']) - 1, -1, -1):
            if 'error' not in r[i] and 'SAD' in r[i]:
                self.SAD = r[i]['SAD']
                break
        else:
            if is_valid:
                self._set_error_level(3)
            raise RuntimeError('*** SAD unavailable ***')
        return self.SAD

    def extend_test(self, sad=None, credential_id=None):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if credential_id is None:
            raise RuntimeError('*** Credential ID unavailable ***')
        if sad is None:
            raise RuntimeError('*** SAD unavailable ***')
        cfg = {
            'service': 'credentials/extendTransaction',
            'tests': [
                { #1 - wrong SAD
                    'name': 'wrong SAD',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': 'xxx',
                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'eq', 'arg': { 'error': 'invalid_request', 'error_description': 'Invalid parameter SAD' } }
                    ]
                },
                { #2
                    'name': 'valid request',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'err_level': 3,
                    'input': {
                        'SAD': sad,
                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'SAD' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }
        r = self._generic_test(cfg)
        for i in range(len(cfg['tests']) - 1, -1, -1):
            if 'error' not in r[i] and 'SAD' in r[i]:
                self.SAD = r[i]['SAD']
                break
        else:
            self._set_error_level(3)
            raise RuntimeError('*** Cannot extend SAD validity ***')
        return self.SAD

    def sign_hash_test(self, sad=None, credential_id=None, key_algo=None):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if sad is None:
            raise RuntimeError('*** SAD unavailable ***')
        cfg = {
            'service': 'signatures/signHash',
            'tests': []
        }
        result_success = [
            { 'condition': 'in', 'arg': [ 'signatures' ] },
            { 'condition': 'not in', 'arg': [ 'error' ] }
        ]
        invalid_digest_length_req = {
            #Erroneous request - invalid digest value length
            'name': 'Invalid digest length',
            'headers': { 'Authorization' : 'Bearer ' + self.session_key },
            'input': {
                'SAD': sad,
                'hash': [
                    '000'
                ],
                'credentialID': credential_id
            },
            'exp_result': [
                { 'condition': 'in', 'arg': [ 'error' ] },
                { 'condition': 'eq', 'arg': { 'error_description': 'Invalid digest value length' } },
                { 'condition': 'not in', 'arg': [ 'signatures' ] }
            ]
        }
        invalid_digest_length_performed = False

        if CSC.ALGO_SHA1_WITH_RSA_ENC in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 4 } })
            base_request = {
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'hash': [
                        CSC.HASH_SHA1_VALUE,
                        CSC.HASH_SHA1_VALUE,
                        CSC.HASH_SHA1_VALUE,
                        CSC.HASH_SHA1_VALUE
                    ],
                    'credentialID': credential_id
                },
                'exp_result': r
            }
            tmp = copy.deepcopy(base_request)
            tmp['name'] = 'sha1 with signAlgo'
            tmp['input']['signAlgo'] = CSC.ALGO_SHA1_WITH_RSA_ENC
            cfg['tests'].append(tmp)
            tmp = copy.deepcopy(base_request)
            tmp['name'] = 'sha1 with generic signAlgo and hashAlgo'
            tmp['input']['signAlgo'] = CSC.ALGO_RSA_ENC
            tmp['input']['hashAlgo'] = CSC.HASH_SHA1_OID
            cfg['tests'].append(tmp)

            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_SHA1_WITH_RSA_ENC
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if CSC.ALGO_SHA224_WITH_RSA_ENC in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 1 } })
            cfg['tests'].append({
                'name': 'sha224 with signAlgo',
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'signAlgo': CSC.ALGO_SHA224_WITH_RSA_ENC,
                    'hash': [ CSC.HASH_SHA224_VALUE ],
                    'credentialID': credential_id
                },
                'exp_result': r
            })
            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_SHA224_WITH_RSA_ENC
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if CSC.ALGO_SHA256_WITH_RSA_ENC in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 1 } })
            cfg['tests'].append({
                'name': 'sha256 with signAlgo',
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'signAlgo': CSC.ALGO_SHA256_WITH_RSA_ENC,
                    'hash': [ CSC.HASH_SHA256_VALUE ],
                    'credentialID': credential_id
                },
                'exp_result': r
            })
            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_SHA256_WITH_RSA_ENC
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if CSC.ALGO_SHA384_WITH_RSA_ENC in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 3 } })
            cfg['tests'].append({
                'name': 'sha384 with signAlgo',
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'signAlgo': CSC.ALGO_SHA384_WITH_RSA_ENC,
                    'hash': [
                        CSC.HASH_SHA384_VALUE,
                        CSC.HASH_SHA384_VALUE,
                        CSC.HASH_SHA384_VALUE
                    ],
                    'credentialID': credential_id
                },
                'exp_result': r
            })
            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_SHA384_WITH_RSA_ENC
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if CSC.ALGO_SHA512_WITH_RSA_ENC in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 1 } })
            cfg['tests'].append({
                'name': 'sha512 with signAlgo',
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'signAlgo': CSC.ALGO_SHA512_WITH_RSA_ENC,
                    'hash': [ CSC.HASH_SHA512_VALUE ],
                    'credentialID': credential_id
                },
                'exp_result': r
            })
            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_SHA512_WITH_RSA_ENC
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if CSC.ALGO_RSASSA_PSS in key_algo:
            r = copy.deepcopy(result_success)
            r.append({ 'condition': '=', 'arg': { 'signatures': 3 } })
            cfg['tests'].append({
                'name': 'RSASSA-PSS with signAlgo',
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'err_level': 3,
                'input': {
                    'SAD': sad,
                    'signAlgoParams': 'MDmgDzANBglghkgBZQMEAgEFAKEcMBoGCSqGSIb3DQEBCDANBglghkgBZQMEAgEFAKIDAgEgowMCAQE=',
                    'signAlgo': CSC.ALGO_RSASSA_PSS,
                    'hash': [
                        CSC.HASH_SHA256_VALUE,
                        CSC.HASH_SHA256_VALUE,
                        CSC.HASH_SHA256_VALUE
                    ],
                    'credentialID': credential_id
                },
                'exp_result': r
            })
            if not invalid_digest_length_performed:
                #Invalid digest value length
                invalid_digest_length_req['input']['signAlgo'] = CSC.ALGO_RSASSA_PSS
                cfg['tests'].append(invalid_digest_length_req)
                invalid_digest_length_performed = True

        if len(cfg['tests']) > 0:
            self._generic_test(cfg)
        else:
            self.logger.warn(CSC.highlight('Unsupported signature algorithms', 'yellow', bold=True))

    def timestamp_test(self):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        cfg = {
            'service': 'signatures/timestamp',
            'tests': [
                { #1
                    'name': 'without nonce',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'hash': 'uB28DAYaAZ+74aWHm30uDgeVB18=',
                        'hashAlgo': '1.3.14.3.2.26'
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'timestamp' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #2
                    'name': 'with nonce',
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'hash': 'uB28DAYaAZ+74aWHm30uDgeVB18=',
                        'hashAlgo': '1.3.14.3.2.26',
                        'nonce': '654654131635468464'
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'timestamp' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }
        self._generic_test(cfg)

    def generic_errors(self):
        cfg = {
            'service': 'unsupported/service',
            'tests': [
                { #1
                    'input': {
                        'key': 'value'
                    },
                    'exp_result': [
                        { 'condition': 'eq', 'arg': { 'error': 'access_denied', 'error_description': 'The user or Remote Service denied the request.' } }
                    ]
                }
            ]
        }
        self._generic_test(cfg)

    def revoke(self, s):
        #REVOKE Test 1
        payload = {
            'token': s
        }
        self.logger.info(CSC.highlight(f'Revoking token {s} ...', bold=True))
        requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        payload = {
            'hash': 'uB28DAYaAZ+74aWHm30uDgeVB18=',
            'hashAlgo': '1.3.14.3.2.26'
        }
        r = requests.post(self.service_URLs['signatures/timestamp'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        j = r.json()
        if 'error' in j:
            self._print_OK_msg('auth/revoke', 1)
        else:
            self._print_KO_msg('Revoke', 1, payload, j)
        #REVOKE Test 2
        if self.credential_encoded is not None:
            payload = {
                'rememberMe': True
            }
            r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
            j = r.json()
            if 'error' not in j:
                sessionKey = j['access_token']
                refreshToken = j['refresh_token']
                payload = {
                    'token': refreshToken
                }
                self.logger.info(CSC.highlight(f'Revoking token {refreshToken} ...', bold=True))
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    payload = {
                        'refresh_token': refreshToken
                    }
                    r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
                    j = r.json()
                    if 'error' in j:
                        self._print_OK_msg('auth/revoke', 2)
                    else:
                        self._print_KO_msg('Revoke', 2, payload, j)
                else:
                    self._set_error_level(2)
                    self.logger.error(CSC.highlight(json.dumps(r.json(), indent=4, sort_keys=True), 'red'))
                    self.logger.error(CSC.highlight('*** Unable to perfom revoke test 2: revoke failed', 'red'))
            else:
                self._set_error_level(2)
                self.logger.error(CSC.highlight('*** Unable to perfom revoke test 2: login failed', 'red'))
        #REVOKE Test 3
        if self.credential_encoded is not None:
            payload = {
                'rememberMe': True
            }
            r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
            j = r.json()
            if 'error' not in j:
                sessionKey = j['access_token']
                refreshToken = j['refresh_token']
                payload = {
                    'token': refreshToken,
                    'token_type_hint': 'refresh_token'
                }
                self.logger.info(CSC.highlight(f'Revoking token {refreshToken} ...', bold=True))
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    payload = {
                        'refresh_token': refreshToken
                    }
                    r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
                    j = r.json()
                    if 'error' in j:
                        self._print_OK_msg('auth/revoke', 3)
                    else:
                        self._print_KO_msg('Revoke', 3, payload, j)
                else:
                    self._set_error_level(2)
                    j = r.json()
                    self.logger.error(CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red'))
                    self.logger.error(CSC.highlight('*** Unable to perfom revoke test 3: revoke failed', 'red'))
            else:
                self._set_error_level(2)
                self.logger.error(CSC.highlight('*** Unable to perfom revoke test 3: login failed', 'red'))
        #REVOKE Test 4
        if self.credential_encoded is not None:
            r = requests.get(self.service_URLs['auth/login'], verify=False, headers={'Authorization': 'Basic ' + self.credential_encoded})
            j = r.json()
            if 'error' not in j:
                sessionKey = j['access_token']
                payload = {
                    'token': sessionKey,
                    'token_type_hint': 'access_token'
                }
                self.logger.info(CSC.highlight(f'Revoking token {sessionKey} ...', bold=True))
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    r = requests.get(self.service_URLs['credentials/list'], verify=False, headers={'Authorization': 'Bearer ' + sessionKey})
                    j = r.json()
                    if 'error' in j:
                        self._print_OK_msg('auth/revoke', 4)
                    else:
                        self._print_KO_msg('Revoke', 4, payload, j)
                else:
                    self._set_error_level(2)
                    j = r.json()
                    self.logger.error(CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red'))
                    self.logger.error(CSC.highlight('*** Unable to perfom revoke test 4: revoke failed', 'red'))
            else:
                self._set_error_level(2)
                self.logger.error(CSC.highlight('*** Unable to perfom revoke test 4: login failed', 'red'))

    def single_revoke(self, token=None, noout=False):
        token = self.session_key if token is None or token == '' else token
        if token is None or token == '':
            self.logger.info(CSC.highlight('Cannot revoke empty token', 'yellow'))
            return
        payload = {
            'token': token
        }
        if not noout:
            self.logger.info(CSC.highlight(f'Revoking token {token} ...', bold=True))
        r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        if r.text != '' and 'error' in r.json():
            self._set_error_level(2)
            j = r.json()
            self.logger.error('{}  {}'.format(CSC.highlight(' \u2190', bold=True), CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red')))
            self.logger.error(CSC.highlight(f'*** Unable to revoke sessionKey {token} ***', 'red', bold=True))

    def _print_OK_msg(self, service, testNum, test_name=None):
        self.logger.info(f'[ {CSC.highlight("OK", "green", bold=True)} ] {service} {"test " + str(testNum) if test_name is None else "- " + test_name}')

    def _print_KO_msg(self, service, testNum, request, response, test_name=None, error_level=2):
        self._set_error_level(error_level)
        self.logger.error(f'[ {CSC.highlight("KO", "red", bold=True)} ] {service} {"test " + str(testNum) if test_name is None else "- " + test_name}')
        self.logger.error('{} {}'.format(CSC.highlight(u' \u2192 ', bold=True), CSC.highlight(json.dumps(request, indent=4, sort_keys=True), 'IndianRed1')))
        self.logger.error('{} {}'.format(CSC.highlight(u' \u2190 ', bold=True), CSC.highlight(json.dumps(response, indent=4, sort_keys=True), 'IndianRed1')))

    @staticmethod
    @logger_style_artist
    def highlight(msg, color='white', bold=False, underline=False):
        if not sys.stdout.isatty():
            return msg
        attr = []
        if bold:
            attr.append('1')
        if underline:
            attr.append('4')
        if not bold and not underline:
            attr.append('0')
        try:
            color = {
                'black':  '90',
                'red':    '91',
                'green':  '92',
                'yellow': '93',
                'blue':   '94',
                'purple': '95',
                'cyan':   '96',
                'white':  '97',
                'DeepPink1':    [ '38', '5', '198' ],
                'DeepSkyBlue2': [ '38', '5', '38'  ],
                'IndianRed1':   [ '38', '5', '203' ],
                'SeaGreen2':    [ '38', '5', '83'  ]
            }[color]
        except KeyError:
            #default to white
            color = '97'
        if isinstance(color, str):
            attr.append(color)
        else:
            attr.extend(color)
        return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), msg)

    def _sig_handler(self, signal, frame):
        signame = {
            2:  'SIGINT',
            15: 'SIGTERM'
        }[signal]
        print(CSC.highlight('\n*** ' + signame + ' detected ***', 'yellow', bold=True), file=sys.stderr)
        if self.SAD is not None and self.SAD != '':
            self.single_revoke(self.SAD)
        if self.session_key is not None and self.session_key != '':
            do_revoke = 'y' if self.quiet else input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            while not re.match('[yYnN]', do_revoke):
                if do_revoke == '':
                    do_revoke = 'y'
                    break
                do_revoke = input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            if re.match('[yY]', do_revoke):
                self.single_revoke(self.session_key)
        sys.exit(1 if self.error_level < 1 else self.error_level)

    def _ask_and_revoke(self, session_key=None):
        do_revoke = 'y' if self.quiet else input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        while not re.match('[yYnN]', do_revoke):
            if do_revoke == '':
                do_revoke = 'y'
                break
            do_revoke = input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        if re.match('[yY]', do_revoke):
            self.single_revoke(self.session_key if session_key is None else session_key)

    def _get_session_key(self):
        r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded })
        if r.text is not None and str(r.text) != '':
            try:
                j = r.json()
            except ValueError:
                self.logger.error(CSC.highlight('Invalid login json response', 'red', bold=True))
                self._set_error_level(1)
                return
        else:
            self.logger.error(CSC.highlight('Invalid login response', 'red', bold=True))
            self._set_error_level(1)
            return

        if 'error' in j or 'access_token' not in j:
            self.logger.error(CSC.highlight('An error occurred during login', 'red', bold=True))
            self.logger.error(CSC.highlight(json.dumps(r.json(), indent=4, sort_keys=True), 'red'))
            self._set_error_level(1)
            return
        return j['access_token']

    def _credential_test_core(self, credential_id, login_executed=False):
        is_valid, auth_mode, pin_presence, otp_presence, otp_type, key_algo = self.get_credential_info(credential_id=credential_id, print_details=True)
        self.credentials_info_test(credential_id, auth_mode)
        if is_valid or self.test_invalid_credentials:
            abort_signature = False
            if auth_mode == 'implicit' or (auth_mode == 'explicit' and otp_presence and otp_type == 'online'):
                if not login_executed or __user__[1].lower() not in self.username:
                    r = 'n' if self.quiet else ''
                    while r != 'y' and r != 'n':
                        r = input(CSC.highlight(f'WARNING! Username could not belong to {" ".join(__user__)}. Continue? [y/n] ', 'yellow', bold=True))
                    if r != 'y':
                        abort_signature = True
            if not abort_signature and auth_mode == 'implicit':
                r = 'n' if self.quiet else ''
                while r != 'y' and r != 'n':
                    r = input(CSC.highlight('Implicit authorization, do you want to continue? [y/n] ', 'yellow', bold=True))
                if r != 'y':
                    abort_signature = True
            elif not self.quiet and not abort_signature and auth_mode in [ 'explicit', 'oauth2code' ] and otp_presence and otp_type == 'online':
                self.send_otp_test(credential_id)

            if not abort_signature:
                self.authorize_test(credential_id, auth_mode, pin_presence, otp_presence, otp_type, 17, is_valid)
                self.extend_test(self.SAD, credential_id)
                self.sign_hash_test(self.SAD, credential_id, key_algo)
        else:
            self.logger.info(CSC.highlight('*** SKIP: invalid credential ***', 'yellow'))

    def check_credential(self, cred_id, ask_revoke=False, login_executed=False):
        r = requests.get(self.service_URLs['info'], verify=False)
        self.logger.info(f'{json.dumps(r.json(), indent=4, sort_keys=True)}')
        login_executed = False
        if not self.session_key:
            self.session_key = self._get_session_key()
            if not self.session_key:
                return
            self.logger.info(CSC.highlight('Using session key ' + self.session_key, 'yellow'))
            login_executed = True
        try:
            self._credential_test_core(cred_id, login_executed)
        except RuntimeError as e:
            self.logger.error(CSC.highlight(e, 'yellow', bold=True))

        if ask_revoke:
            do_revoke = 'y' if self.quiet else input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            while not re.match('[yYnN]', do_revoke):
                if do_revoke == '':
                    do_revoke = 'y'
                    break
                do_revoke = input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            if re.match('[yY]', do_revoke):
                self.single_revoke(self.session_key)

    def global_test(self):
        self.info_test()
        self.generic_errors()
        login_executed = False
        if not self.session_key:
            login_executed = True
            try:
                self.login_test()
            except RuntimeError as e:
                self.logger.error(CSC.highlight(e, 'red', bold=True))
                sys.exit(self.error_level)
        self.logger.info(CSC.highlight('Using session key ' + self.session_key, 'yellow'))
        self.timestamp_test()
        self.list_test()
        if self.test_credentials and len(self.credential_IDs) > 0:
            self.logger.info(CSC.highlight(f'{str(len(self.credential_IDs))} credential{"" if len(self.credential_IDs) == 1 else "s"} found', bold=True))
            self.logger.info(f'{CSC.highlight("Credentials IDs:", bold=True)} {CSC.highlight(json.dumps(self.credential_IDs, indent=4, sort_keys=True), "DeepSkyBlue2")}')
            for c in self.credential_IDs:
                try:
                    self._credential_test_core(c, login_executed)
                except RuntimeError as e:
                    self.logger.error(CSC.highlight(e, 'yellow', bold=True))
        elif not self.test_credentials:
            self.logger.warn(CSC.highlight('*** SKIPPING CREDENTIALS TESTS ***', 'yellow'))
        else:
            self.logger.warn(CSC.highlight('*** No credentials found! ***', 'yellow'))

        do_revoke = 'y' if self.quiet else input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        while not re.match('[yYnN]', do_revoke):
            if do_revoke == '':
                do_revoke = 'y'
                break
            do_revoke = input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        if re.match('[yY]', do_revoke):
            self.revoke(self.refresh_token if self.refresh_token is not None else self.session_key)

    def scan(self):
        if not self.session_key:
            self.session_key = self._get_session_key()
            if not self.session_key:
                return

        self.logger.info(CSC.highlight(f'Using session key {self.session_key}', 'yellow'))
        credentials_ids = self.list_utility(64)
        if len(credentials_ids) > 0:
            self.logger.info(CSC.highlight(f'{str(len(credentials_ids))} credential{"" if len(credentials_ids) == 1 else "s"} found', bold=True))
            self.logger.info(f'{CSC.highlight("Credentials IDs:", bold=True)} {CSC.highlight(json.dumps(credentials_ids, indent=4, sort_keys=True), "DeepSkyBlue2")}')
            for c in credentials_ids:
                try:
                    self.get_credential_info(credential_id=c, print_details=True, certificates='single')
                except RuntimeError as e:
                    self.logger.error(CSC.highlight(f'An error occurred while getting info for credential {c} - {str(e)}', 'red', bold=True))
        else:
            self.logger.warn(CSC.highlight('No credentials found', 'red', bold=True))
        self._ask_and_revoke()

    @staticmethod
    def _check_logo(env_name, url, allow_redir=True):
        p = re.compile("^.+\.([^.]+)$")
        content_types = {
            "jpeg": "image/jpeg",
            "jpg":  "image/jpeg",
            "png":  "image/png"
        }
        try:
            m = p.search(url)
            r = requests.get(url, allow_redirects=allow_redir)
            if r is None:
                return f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test {CSC.highlight(env_name, color="DeepSkyBlue2")} failed for URL [ {url} ]: {CSC.highlight("info response is empty", color="yellow")}'
            elif r.status_code != 200:
                return f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test {CSC.highlight(env_name, color="DeepSkyBlue2")} failed for URL [ {url} ]: {CSC.highlight("status_code " + str(r.status_code), color="yellow")}'
            elif m.group(1) in content_types and r.headers['content-type'] != content_types[m.group(1)]:
                return f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test {CSC.highlight(env_name, color="DeepSkyBlue2")} failed for URL [ {url} ]: {CSC.highlight("content-type " + r.headers["content-type"], color="yellow")}'
            elif m.group(1) not in content_types:
                return f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test {CSC.highlight(env_name, color="DeepSkyBlue2")} failed for URL [ {url} ]: {CSC.highlight("Unable to check content-type " + r.headers["content-type"], color="yellow")}'
            else:
                return f'[ {CSC.highlight("OK", color="green", bold=True)} ] {CSC.highlight(env_name, underline=True)} URL [ {url} ]'
        except Exception as e:
            return f'[ {CSC.highlight("KO", color="red", bold=True)} ] Logo test {CSC.highlight(env_name, color="DeepSkyBlue2")} failed for URL [ {url} ]: {CSC.highlight("an exception has been thrown", color="yellow")}\n{e}'

    @staticmethod
    def check_logos(logger=None):
        err_func = logger.error if logger else print
        info_func = logger.info if logger else print
        error_level = 0
        info_func(CSC.highlight('Checking service logos', bold=True))
        for k, v in CSC.service_logo_URLs.items():
            s = CSC._check_logo(k, v)
            if 'KO' in s:
                error_level = 2
                err_func(s)
            else:
                info_func(s)
        info_func(CSC.highlight('\nChecking OAuth logos', bold=True))
        for k, v in CSC.oauth_logo_URLs.items():
            s = CSC._check_logo(k, v)
            if 'KO' in s:
                error_level = 2
                err_func(s)
            else:
                info_func(s)
        return error_level

    def _set_error_level(self, value):
        if not self.error_level or self.error_level < value:
            self.error_level = value

    def get_error_level(self):
        self.logger.info(f'DEBUG - exit value {self.error_level}') # TODO remove
        return self.error_level

    def __init__(self, user=None, passw='password', pin='12345678', env=None, context=None, session_key=None, quiet=False, logger=None, noout=False):
        #ctx = ssl.create_default_context()
        #ctx.check_hostname = False
        #ctx.verify_mode = ssl.CERT_NONE

        self.logger = logger if logger else get_logger()

        if not env and not context:
            raise RuntimeError('Missing CSC environment or context')
        if not context and env not in CSC.env_URLs:
            raise RuntimeError('Invalid CSC environment')
        if not context:
            context = CSC.env_URLs[env]

        self.service_URLs = {
            'info':                          context + '/info',
            'auth/login':                    context + '/auth/login',
            'auth/revoke':                   context + '/auth/revoke',
            'credentials/list':              context + '/credentials/list',
            'credentials/info':              context + '/credentials/info',
            'credentials/sendOTP':           context + '/credentials/sendOTP',
            'credentials/authorize':         context + '/credentials/authorize',
            'credentials/extendTransaction': context + '/credentials/extendTransaction',
            'signatures/signHash':           context + '/signatures/signHash',
            'signatures/timestamp':          context + '/signatures/timestamp',
            'oauth2/authorize':              context + '/oauth2/authorize',
            'oauth2/token':                  context + '/oauth2/token',
            'unsupported/service':           context + '/unsupported/service'
        }

        self.test_credentials = True
        self.test_invalid_credentials = True

        self.username = user

        self.credential_encoded = None if not user else base64.b64encode(bytes(f'{self.username}:{passw}', 'utf-8')).decode('utf-8')
        self.session_key = session_key
        self.refresh_token = None
        self.DEFAULT_PIN = pin
        self.SAD = None
        self.error_level = 0
        self.quiet = quiet

        if not noout:
            self.logger.debug(CSC.getinfostr())
            self.logger.info(f'{CSC.highlight("Using endpoint:", bold=True)} {CSC.highlight(context, underline=True)}')
            if self.username is not None:
                self.logger.info(f'{CSC.highlight("Using account:", bold=True)} {CSC.highlight(self.username, "DeepSkyBlue2")}')
            if self.credential_encoded is not None:
                self.logger.debug(f'{CSC.highlight("Using authorization header:", bold=True)} {self.credential_encoded}')
            self.logger.debug('\n###\n')

            signal.signal(signal.SIGINT,  self._sig_handler)
            signal.signal(signal.SIGTERM, self._sig_handler)

        if 'https' in context:
            try:
                requests.packages.urllib3.disable_warnings()
            except:
                self.logger.info(CSC.highlight('Unable to disable urlib3 warnings', 'yellow'))
                self.logger.info(CSC.highlight('Update \'requests` module or execute `export PYTHONWARNINGS="ignore:Unverified HTTPS request"` to suppress HTTPS warnings', 'yellow'))

def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(CSC.getinfostr())
    ctx.exit(0)

def validate_session(ctx, param, value):
    if value and ctx.params['environment'] is None:
        raise click.BadParameter(f'Cannot use session [{value}], missing environment value')
    return value

def initialize_with_TUI(quiet, logger, noout=False):
    m = CSCCursesMenu(CSCCursesMenu.DEFAULT_CREDENTIALS_FILE_NAME)
    try:
        data = m.display()
    except curses.error:
        m.destroy()
        logger.error(CSC.highlight('An error occurred: please increase window size', 'red', bold=True))
        sys.exit(1)
    except Exception as e:
        m.destroy()
        traceback.print_exc()
        sys.exit(1)
    finally:
        if not curses.isendwin():
            m.destroy()
    if not data:
        logger.error(CSC.highlight('A problem occurred while getting data from the TUI', 'red', bold=True))
        sys.exit(1)

    return CSC(data['username'], data['password'], context=data['ctx_path'], session_key=data['session_key'], quiet=quiet, logger=logger, noout=noout)

@click.group(context_settings=dict(help_option_names=['-h', '--help']), invoke_without_command=True)
@click.option('--user',        '-u', metavar='<username>', help='Account username to be used.')
@click.option('--passw',       '-p', metavar='<password>', help='Account password to be used.')
@click.option('--environment', '-e', metavar='<env>', is_eager=True, type=click.Choice(CSC.env_URLs.keys()), help='Target environment. Use the list command to view the supported environments.')
@click.option('--session',     '-s', metavar='<session-key>', callback=validate_session, help='A valid CSC access token. If provided, no authentication using username/password will be performed.')
@click.option('--quiet',       '-q', is_flag=True, default=False, help='Non-interactive mode: every test requiring a user interaction will be skipped. Only automatic credentials (PIN only) will be checked using the default PIN. WARNING the default PIN is 12345678.')
@click.option('--log',         '-l', type=click.Path(exists=False, resolve_path=True), metavar='<path-to-log-file>', help='Log file path. If present, the output will be written to this file. If not, no log file will be created and STDOUT will be used.')
@click.option('--version',     '-V', is_flag=True, expose_value=False, callback=print_version, is_eager=True, help='Print version information and exit.')
@click.pass_context
def main(ctx, quiet, user, passw, environment, session, log):

    """
    Utility script for Cloud Signature Consortium (CSC) API testing.

    \b
    If username/password, session or environment are not provided, a text user interface (TUI) will be shown.

    \b
    Returned values:
     0 \u2192  OK
     1 \u2192  Error: the script couldn't run properly (e.g. invalid login credentials)
     2 \u2192  Error: one or more minor checks failed (e.g. wrong error messages)
     3 \u2192  Critical error: core signature functionalities are compromised

    ARGS: with `check' command, the credential ID(s) to be tested. If no credential ID is provided then check every credential found in the account and perform other non credential-related checks.

    \b
    With `otp' command, a single credential ID is expected.
    """

    ctx.ensure_object(dict)
    logger = get_logger(log)

    # default command = `check'
    if ctx.invoked_subcommand is None:
        if not environment or (not user or not passw) and not session:
            csc = initialize_with_TUI(quiet, logger)
        else:
            csc = CSC(user, passw, env=environment, session_key=session, quiet=quiet, logger=logger)
        csc.global_test()
        sys.exit(csc.get_error_level())

    ctx.obj['environment'] = environment
    ctx.obj['logger'] = logger
    ctx.obj['password'] = passw
    ctx.obj['quiet'] = quiet
    ctx.obj['session'] = session
    ctx.obj['user'] = user

@main.command('list')
def list_environments():
    """List the available environments and exit"""
    align_len = max([ len(CSC.highlight(c, "DeepSkyBlue2")) for c in CSC.env_URLs.keys() ]) + 1 # dinamically get the alignment size
    print(*[ f'{CSC.highlight(c, "DeepSkyBlue2"):>{align_len}} \u2192  {CSC.env_URLs[c]}' for c in sorted(CSC.env_URLs.keys()) ], sep='\n')
    sys.exit(0)

@main.command()
@click.pass_context
def logo(ctx):
    """Check logo files and exit"""
    sys.exit(CSC.check_logos(ctx.obj['logger']))

@main.command(short_help='Scan the user credentials: no signature test will be performed, only the credential details will be shown.')
@click.pass_context
def scan(ctx):
    if not ctx.obj['environment'] or (not ctx.obj['user'] or not ctx.obj['password']) and not ctx.obj['session']:
        csc = initialize_with_TUI(quiet=ctx.obj['quiet'], logger=ctx.obj['logger'])
    else:
        csc = CSC(ctx.obj['user'], ctx.obj['password'], env=ctx.obj['environment'], session_key=ctx.obj['session'], quiet=ctx.obj['quiet'], logger=ctx.obj['logger'])
    csc.scan()
    sys.exit(csc.get_error_level())

@main.command(short_help='Check credential ID(s) provided: if no credential ID is provided then check every credential found in the account and perform other non credential-related checks')
@click.argument('credential_id', nargs=-1)
@click.pass_context
def check(ctx, credential_id):
    if not ctx.obj['environment'] or (not ctx.obj['user'] or not ctx.obj['password']) and not ctx.obj['session']:
        csc = initialize_with_TUI(quiet=ctx.obj['quiet'], logger=ctx.obj['logger'])
    else:
        csc = CSC(ctx.obj['user'], ctx.obj['password'], env=ctx.obj['environment'], session_key=ctx.obj['session'], quiet=ctx.obj['quiet'], logger=ctx.obj['logger'])
    if len(credential_id) > 0:
        for i in range(len(credential_id)):
            csc.check_credential(credential_id[i], ask_revoke=(i == len(credential_id) - 1), login_executed=(i > 0))
    else:
        csc.global_test()
    sys.exit(csc.get_error_level())

@main.command()
@click.argument('credential_id', nargs=1)
@click.pass_context
def otp(ctx, credential_id):
    """Send the OTP for a credential passed as an argument"""
    if not ctx.obj['environment'] or (not ctx.obj['user'] or not ctx.obj['password']) and not ctx.obj['session']:
        csc = initialize_with_TUI(quiet=ctx.obj['quiet'], logger=ctx.obj['logger'], noout=True)
    else:
        csc = CSC(ctx.obj['user'], ctx.obj['password'], env=ctx.obj['environment'], session_key=ctx.obj['session'], quiet=ctx.obj['quiet'], logger=ctx.obj['logger'], noout=True)
    csc.send_otp(credential_id)
    sys.exit(csc.get_error_level())

if __name__ == "__main__":
    main()

