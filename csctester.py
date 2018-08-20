#!/usr/bin/env python2
# -*- coding: utf-8 -*-

__author__  = 'Davide Barelli'
__email__   = 'dbarelli@wersec.com'
__version__ = '1.1.0'

from collections import OrderedDict
from operator import itemgetter
from shutil import copy
import base64
import curses
import getpass
import json
import os
import re
import requests
import signal
#import ssl
import sys
import tempfile
import traceback

class CSCCursesMenu(object):

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
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)

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

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_file_path = '{}/{}'.format(self.script_dir, config_file_name)
        try:
            f = open(self.config_file_path, 'r')
        except:
            self.conf_file = False
            self.users_data = {}
        else:
            self.conf_file = True
            with f:
                self.users_data = json.load(f)

    def prompt_selection(self, parent=None):
        sub_menu = self.menu['selected']
        if not parent:
            if 'parent' in self.menu[sub_menu]:
                back_option = "Return to previous menu ({})".format(self.menu[sub_menu]['parent'].title())
            else:
                back_option = None
        else:
            back_option = "Return to previous menu ({})".format(parent['title'])

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
            self.screen.clear()
            self.screen.border(0)
            self._draw_title()
            self._draw_status_bar("Press 'h' for help")
            for option in range(option_count):
                if self.selected_option == option:
                    self._draw_option(option, self.hilite_color)
                else:
                    self._draw_option(option, self.normal_color)

            if self.selected_option == option_count:
                self.screen.addstr(self.curr_ord + option_count + 1, 4, "{}".format(exit_option if not back_option else back_option), self.hilite_color)
            else:
                self.screen.addstr(self.curr_ord + option_count + 1, 4, "{}".format(exit_option if not back_option else back_option), self.normal_color)

            if back_option is not None:
                if self.selected_option == option_count + 1:
                    self.screen.addstr(self.curr_ord + option_count + 2, 4, "{}".format(exit_option), self.hilite_color)
                else:
                    self.screen.addstr(self.curr_ord + option_count + 2, 4, "{}".format(exit_option), self.normal_color)

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
                           "{}".format(self.menu[sub_menu]['options'][option_number]['title']),
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
            if 'style' in row:
                for row_style in row['style']:
                    self.screen.attron(row_style)
            self.screen.addstr(self.curr_ord, 2, row['text'])
            if 'style' in row:
                for row_style in row['style']:
                    self.screen.attroff(row_style)
            if len(subtitle) > 1:
                self.curr_ord += 1
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
        sub_menu['options'] = []
        for e in CSC.env_IDs:
            sub_menu['options'].append({
                'title': e.title(),
                'value': e
            })
        self.environment_name = None
        self.v_host_ctx_path  = None

    def _load_virtual_host_menu(self):
        self.menu['selected'] = 'virtual_host'
        sub_menu = self.menu['virtual_host']
        sub_menu['options'] = []
        for v in CSC.virtual_host:
            if self.environment_name in CSC.virtual_host[v]:
                sub_menu['options'].append({
                    'title': v.title(),
                    'value': v
                })
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
                'text': '{} > {}'.format(cache['username'], cache['ctx_path']),
                'style': [
                    curses.A_BOLD,
                    self.blue_color
                ]
            }
        ]
        selected_option = self.prompt_selection()
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
        self.screen.addstr(1, 2, 'CSC Tester ' + __version__ + ' - 2018 Davide Barelli')
        self.screen.attroff(self.red_color)
        self.screen.attron(self.cyan_color)
        self.screen.addstr(4, 2, '{:>18}'.format('J j DOWN_ARROW:'))
        self.screen.addstr(5, 2, '{:>18}'.format('K k UP_ARROW:'))
        self.screen.addstr(6, 2, '{:>18}'.format('ENTER RIGHT_ARROW:'))
        self.screen.addstr(7, 2, '{:>18}'.format('B b LEFT_ARROW:'))
        self.screen.addstr(8, 2, '{:>18}'.format('Q q:'))
        self.screen.addstr(9, 2, '{:>18}'.format('H h:'))
        self.screen.attroff(self.cyan_color)
        self.screen.addstr(4, 21, 'down'.format('J j:'))
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
                selected_option = self.prompt_selection()
                if selected_option is len(sub_menu['options']):
                    self.destroy()
                    return None
                env = sub_menu['options'][selected_option]
                self.environment_name = env['value']
            elif not self.v_host_ctx_path:
                #virtual host
                self._load_virtual_host_menu()
                sub_menu = self.menu['virtual_host']
                selected_option = self.prompt_selection()
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
                selected_option = self.prompt_selection()
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
                    if 'password' in e and password != e['password']:
                        e['name'].remove(self.environment_name)
                    elif 'password' not in e and password != 'password':
                        e['name'].remove(self.environment_name)
                    else:
                        return True
                    if len(e['name']) is 0:
                        user['environment'].remove(e)
                    for ee in user['environment']:
                        if 'password' in ee and password == ee['password']:
                            ee['name'].append(self.environment_name)
                            return True
                    break
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
            tmp_backup_file = '{}/{}'.format(tempfile.gettempdir(), next(tempfile._get_candidate_names()))
            try:
                copy(self.config_file_path, tmp_backup_file)
            except Exception as e:
                print CSC.highlight('An error occurred while creating a backup file', 'red', bold=True), e
                return False
        try:
            open(self.config_file_path, 'w').close()
            with open(self.config_file_path, 'w') as f:
                f.write(json.dumps(content, indent=4, sort_keys=True))
        except Exception as e:
            print CSC.highlight('An error occurred while updating your configuration file', 'yellow'), e
            if self.conf_file:
                try:
                    print CSC.highlight('Restoring the old configuration', 'yellow')
                    copy(tmp_backup_file, self.config_file_path)
                except:
                    print CSC.highlight('Cannot restore configuration file, a backup file has been saved in path ' + tmp_backup_file, 'red', bold=True)
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
        self.screen.addstr(max_y - 2, 1, ('{: >' + str(max_x - 3) + '}').format(message) + ' ', self.status_bar_color)
        return True

    def _get_string(self, label, draw_title=True):
        self.screen.clear()
        if draw_title:
            self._draw_title('')
        curses.echo()
        curses.curs_set(1)
        _, max_x = self.screen.getmaxyx()
        self.screen.border(0)
        self.screen.addstr(self.curr_ord + 2, max_x/3 - len(label), label, curses.A_BOLD)
        self._draw_status_bar('Insert an empty string to go back')
        self.screen.refresh()
        try:
            val = self.screen.getstr(self.curr_ord + 2, max_x/3 + 1, max_x - 2 - max_x/3 - 1)
            return val.strip()
        except:
            return None
        finally:
            curses.noecho()
            curses.curs_set(0)

    def destroy(self):
        self.running = False
        curses.endwin()


class CSC(object):

    env_IDs = [
        'localhost',
        'integrazione',
        'integrazione78',
        'integrazione79',
        'collaudo',
        'produzione',
        'disaster recovery',
        'transsped (produzione)'
    ]

    virtual_host = OrderedDict([
        ('time4mind', {
            'localhost': 'http://localhost:8080/Time4UserServices/csc/v1',
            'integrazione': 'https://services.int4mind.com/csc/v1',
            'integrazione78': 'http://192.168.0.78:8080/Time4UserServices/csc/v1',
            'integrazione79': 'http://192.168.0.79:8080/Time4UserServices/csc/v1',
            'collaudo': 'https://services.test4mind.com/csc/v1',
            'produzione': 'https://services.time4mind.com/csc/v1',
            'disaster recovery': 'https://services-dr.time4mind.com/csc/v1'
        }),
        ('globalsign', {
            'localhost': 'http://localhost:8080/Time4UserServices/csc/globalsign/v1',
            #'integrazione': 'https://globalsign.int4mind.com/csc/v1',
            'integrazione78': 'http://192.168.0.78:8080/Time4UserServices/csc/globalsign/v1',
            'integrazione79': 'http://192.168.0.79:8080/Time4UserServices/csc/globalsign/v1',
            'collaudo': 'https://globalsign.test4mind.com/csc/v1',
            'produzione': 'https://globalsign.time4mind.com/csc/v1',
            'disaster recovery': 'https://globalsign-dr.time4mind.com/csc/v1'
        }),
        ('bankid-no', {
            'localhost': 'http://localhost:8080/Time4UserServices/csc/bankidno/v1',
            #'integrazione': 'https://bankidno.int4mind.com/csc/v1',
            'integrazione78': 'http://192.168.0.78:8080/Time4UserServices/csc/bankidno/v1',
            'integrazione79': 'http://192.168.0.79:8080/Time4UserServices/csc/bankidno/v1',
            'collaudo': 'https://bankidno.test4mind.com/csc/v1',
            'produzione': 'https://bankidno.time4mind.com/csc/v1',
            'disaster recovery': 'https://bankidno-dr.time4mind.com/csc/v1'
        }),
        ('bankid-sw', {
            'localhost': 'http://localhost:8080/Time4UserServices/csc/bankid/v1',
            #'integrazione': 'https://bankid.int4mind.com/csc/v1',
            'integrazione78': 'http://192.168.0.78:8080/Time4UserServices/csc/bankid/v1',
            'integrazione79': 'http://192.168.0.79:8080/Time4UserServices/csc/bankid/v1',
            'collaudo': 'https://bankid.test4mind.com/csc/v1',
            'produzione': 'https://bankid.time4mind.com/csc/v1',
            'disaster recovery': 'https://bankid-dr.time4mind.com/csc/v1'
        }),
        ('transsped', {
            'transsped (produzione)': 'https://services.cloudsignature.online/csc/v1'
        })
    ])

    env_URLs = {
        'localhost':        'http://localhost:8080/Time4UserServices/csc/v1',

        'integrazione':     'https://services-int.time4mind.com/csc/v1',
        'integrazione-new': 'https://services.int4mind.com/csc/v1',
        'integrazione78':   'http://192.168.0.78:8080/Time4UserServices/csc/v1',
        'integrazione79':   'http://192.168.0.79:8080/Time4UserServices/csc/v1',
        'transsped-78':     'http://192.168.0.78:8080/Time4UserServices/csc/transsped/v1',
        'transsped-int':    'https://transsped-int.time4mind.com/csc/v1',

        'adobe-col':        'https://adobe.test4mind.com/csc/v1',
        'bankid-col':       'https://bankid.test4mind.com/csc/v1',
        'bankidno-col':     'https://bankidno.test4mind.com/csc/v1',
        'collaudo':         'https://services.test4mind.com/csc/v1',
        'globalsign-col':   'https://globalsign.test4mind.com/csc/v1',
        'transsped-col':    'https://transsped.test4mind.com/csc/v1',

        'adobe':            'https://adobe.time4mind.com/csc/v1',
        'bankid':           'https://bankid.time4mind.com/csc/v1',
        'globalsign':       'https://globalsign.time4mind.com/csc/v1',
        'produzione':       'https://services.time4mind.com/csc/v1',
        'transsped':        'https://services.cloudsignature.online/csc/v1',

        'adobe-dr':         'https://adobe-dr.time4mind.com/csc/v1',
        'bankid-dr':        'https://bankid-dr.time4mind.com/csc/v1',
        'dr':               'https://services-dr.time4mind.com/csc/v1',
        'globalsign-dr':    'https://globalsign-dr.time4mind.com/csc/v1',
        'transsped-dr':     'https://transsped-dr.time4mind.com/csc/v1'
    }

    service_logo_URLs = OrderedDict([
        #old
        ('intesi-prod',        'https://www.time4mind.com/resource/img/logo_IG_symbol.png'), #TODO remove /var/www/t4mind/resource/img/logo_IG_symbol.jpg
        ('transsped-prod',     'https://www.time4mind.com/resource/img/csc_transsped.png'), #TODO remove /var/www/t4mind/resource/img/csc_transsped.jpg

        #new
        ('adobe-col',          'https://services.test4mind.com/res_ext/vendors/adobe/csc_adobe.jpg'),
        ('bankid-col',         'https://services.test4mind.com/res_ext/vendors/bankid/csc_bankid.jpg'),
        ('bankidno-col',       'https://services.test4mind.com/res_ext/vendors/bankidno/csc_bankidno.jpg'),
        ('globalsign-col',     'https://services.test4mind.com/res_ext/vendors/globalsign/csc_globalsign.png'),
        ('intesi-col',         'https://services.test4mind.com/res_ext/logo_IG_symbol.png'),
        ('transsped-col',      'https://services.test4mind.com/res_ext/vendors/transsped/csc_transsped.png'),

        ('adobe-prod',         'https://services.time4mind.com/res_ext/vendors/adobe/csc_adobe.jpg'),
        ('bankid-prod',        'https://services.time4mind.com/res_ext/vendors/bankid/csc_bankid.jpg'),
        ('bankidno-prod',      'https://services.time4mind.com/res_ext/vendors/bankidno/csc_bankidno.jpg'),
        ('globalsign-prod',    'https://services.time4mind.com/res_ext/vendors/globalsign/csc_globalsign.png'),
        ('intesi-prod-new',    'https://services.time4mind.com/res_ext/logo_IG_symbol.png'),
        ('transsped-prod-new', 'https://services.time4mind.com/res_ext/vendors/transsped/csc_transsped.png'),

        ('adobe-dr',           'https://services-dr.time4mind.com/res_ext/vendors/adobe/csc_adobe.jpg'),
        ('bankid-dr',          'https://services-dr.time4mind.com/res_ext/vendors/bankid/csc_bankid.jpg'),
        ('bankidno-dr',        'https://services-dr.time4mind.com/res_ext/vendors/bankidno/csc_bankidno.jpg'),
        ('globalsign-dr',      'https://services-dr.time4mind.com/res_ext/vendors/globalsign/csc_globalsign.png'),
        ('intesi-dr',          'https://services-dr.time4mind.com/res_ext/logo_IG_symbol.png'),
        ('transsped-dr',       'https://services-dr.time4mind.com/res_ext/vendors/transsped/csc_transsped.png')
    ])

    oauth_logo_URLs = OrderedDict([
        #old
        ('transsped-prod',     'https://www.time4mind.com/resource/CSC_OAUTH_resources/vendors/transsped/img/faviconX180.png'), #TODO remove

        #new
        ('bankid-col',         'https://services.test4mind.com/res_ext/vendors/bankid/img/oauthLogo.png'),
        ('bankidno-col',       'https://services.test4mind.com/res_ext/vendors/bankidno/img/oauthLogo.png'),
        ('globalsign-col',     'https://services.test4mind.com/res_ext/vendors/globalsign/img/oauthLogo.png'),
        ('intesi-col',         'https://services.test4mind.com/res_ext/img/faviconX180.png'), #XXX ???
        ('transsped-col-new',  'https://services.test4mind.com/res_ext/vendors/transsped/img/oauthLogo.png'),

        ('bankid-prod',        'https://services.time4mind.com/res_ext/vendors/bankid/img/oauthLogo.png'),
        ('bankidno-prod',      'https://services.time4mind.com/res_ext/vendors/bankidno/img/oauthLogo.png'),
        ('globalsign-prod',    'https://services.time4mind.com/res_ext/vendors/globalsign/img/oauthLogo.png'),
        ('intesi-prod',        'https://services.time4mind.com/res_ext/faviconX180.png'), #XXX ???
        ('transsped-prod-new', 'https://services.time4mind.com/res_ext/vendors/transsped/img/oauthLogo.png'),

        ('bankid-dr',          'https://services-dr.time4mind.com/res_ext/vendors/bankid/img/oauthLogo.png'),
        ('bankidno-dr',        'https://services-dr.time4mind.com/res_ext/vendors/bankidno/img/oauthLogo.png'),
        ('globalsign-dr',      'https://services-dr.time4mind.com/res_ext/vendors/globalsign/img/oauthLogo.png'),
        ('intesi-dr',          'https://services-dr.time4mind.com/res_ext/faviconX180.png'), #XXX ???
        ('transsped-dr',       'https://services-dr.time4mind.com/res_ext/vendors/transsped/img/oauthLogo.png')
    ])

    @staticmethod
    def tool_info():
        print '                 _            _            '
        print '                | |          | |           '
        print '  ___ ___  ___  | |_ ___  ___| |_ ___ _ __ '
        print ' / __/ __|/ __| | __/ _ \/ __| __/ _ \ \'__|'
        print '| (__\__ \ (__  | ||  __/\__ \ ||  __/ |   '
        print ' \___|___/\___|  \__\___||___/\__\___|_|   ', '\n\n'
        print CSC.highlight('Version:', bold=True), __version__

    def generic_test(self, cfg):
        tests = cfg['tests']
        response = []
        for i in xrange(0, len(tests), 1):
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
                    print '[', CSC.highlight('KO', 'red', bold=True), '] -', cfg['service'] + ' test', i + 1, ': cannot parse json response\n'
                    return []
            check = t['exp_result']
            fail = False
            def in_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for a in c['arg']:
                    if '>' in a:
                        chunks = a.split('>')
                        tmp = j
                        for cc in chunks:
                            if cc in tmp:
                                tmp = tmp[cc]
                            else:
                                return True
                    elif a not in j or j[a] is None:
                        return True
                return False

            def not_in_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for a in c['arg']:
                    if '>' in a:
                        chunks = a.split('>')
                        tmp = j
                        found = True
                        for cc in chunks:
                            if cc not in tmp or tmp[cc] is None:
                                found = False
                                break
                            tmp = tmp[cc]
                        if found:
                            return True
                    elif a in j and j[a] is not None:
                        return True
                return False

            def equal_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if key not in j or not re.match(c['arg'][key], j[key]):
                        return True
                return False

            def not_equal_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if key in j and j[key] == c['arg'][key]:
                        return True
                return False

            def len_lesser_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if '>' in key:
                        chunks = key.split('>')
                        tmp = j
                        for cc in chunks:
                            if cc in tmp:
                                tmp = tmp[cc]
                            else:
                                return True
                        if not isinstance(tmp, list) or len(tmp) >= c['arg'][key]:
                            return True
                    elif key not in j or not isinstance(j[key], list) or len(j[key]) >= c['arg'][key]:
                        return True
                return False

            def len_eq_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if '>' in key:
                        chunks = key.split('>')
                        tmp = j
                        for cc in chunks:
                            if cc in tmp:
                                tmp = tmp[cc]
                            else:
                                return True
                        if not isinstance(tmp, list) or len(tmp) != c['arg'][key]:
                            return True
                    elif key not in j or not isinstance(j[key], list) or len(j[key]) != c['arg'][key]:
                        return True
                return False

            def len_greater_callback():
                if 'arg' not in c or c['arg'] is None:
                    return False
                for key in c['arg']:
                    if '>' in key:
                        chunks = key.split('>')
                        tmp = j
                        for cc in chunks:
                            if cc in tmp:
                                tmp = tmp[cc]
                            else:
                                return True
                        if not isinstance(tmp, list) or len(tmp) <= c['arg'][key]:
                            return True
                    elif key not in j or not isinstance(j[key], list) or len(j[key]) <= c['arg'][key]:
                        return True
                return False

            for c in check:
                try:
                    fail = {
                        'in': in_callback,
                        'not in': not_in_callback,
                        'eq': equal_callback,
                        'not eq': not_equal_callback,
                        '<': len_lesser_callback,
                        '=': len_eq_callback,
                        '>': len_greater_callback
                    }[c['condition']]()
                except Exception as e:
                    #print 'error', CSC.highlight(e, 'yellow', bold=True)
                    print CSC.highlight('Invalid condition check: ' + c['condition'], 'yellow', bold=True), e
                if fail:
                    break

            if fail:
                CSC.printKOmsg(cfg['service'], i + 1, t['input'], j)
            else:
                CSC.printOKmsg(cfg['service'], i + 1)
            response.append(j)
        return response

    def info_test(self):
        r = requests.get(self.service_URLs['info'], verify=False)
        j = r.json()
        print json.dumps(j, indent=4, sort_keys=True) + '\n'
        if 'logo' in j:
            #check logo existence
            rr = requests.get(j['logo'], allow_redirects=False)
            if rr is None:
                print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test failed:', CSC.highlight('info response is empty', color='yellow')
            elif rr.status_code != 200:
                print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test failed:', CSC.highlight('status_code ' + str(rr.status_code), color='yellow')
            elif rr.headers['Content-Type'] != 'image/png' and rr.headers['Content-Type'] != 'image/jpeg':
                print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test failed:', CSC.highlight('content type ' + str(rr.headers['Content-Type']), color='yellow')
            else:
                print '[', CSC.highlight('OK', color='green', bold=True), '] - Logo test'
        else:
            print CSC.highlight('Logo URL not present', color='yellow', bold=True)
        cfg = {
            'service': 'info',
            'tests': [
                {
                    'input': None,
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'lang': 'en-US' }, }
                    ]
                },
                {
                    'input': { 'lang': 'it-IT' },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'lang': 'it-IT' }, }
                    ]
                }
            ]
        }
        self.generic_test(cfg)

    def login_test(self):
        if self.session_key is not None:
            print CSC.highlight('Login disabled. Using configured sessionkey:', bold=True), self.session_key
            return
        if self.credential_encoded is None:
            raise RuntimeError('*** Encoded credentials unavailable ***')
        cfg = {
            'service': 'auth/login',
            'tests': [
                { #1
                    'headers': { 'Authorization' : 'Basic ' + self.credential_encoded },
                    'input': None,
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'access_token' ] },
                        { 'condition': 'not in', 'arg': [ 'refresh_token', 'error' ] }
                    ]
                },
                { #2
                    'headers': { 'Authorization' : 'Basic ' + self.credential_encoded },
                    'input': { 'rememberMe': True },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'access_token', 'refresh_token' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }
        r = self.generic_test(cfg)
        self.session_key = None
        self.refresh_token = None
        found = False
        #save access_token/refresh_token and revoke the others
        for i in xrange(len(cfg['tests']) - 1, -1, -1):
            if not found and 'error' not in r[i] and 'access_token' in r[i]:
                self.session_key = r[i]['access_token']
                if 'refresh_token' in r[i]:
                    self.refresh_token = r[i]['refresh_token']
                found = True
            elif 'access_token' in r[i]:
                self.single_revoke(r[i]['access_token'])
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        return self.session_key, self.refresh_token

    def list_test(self):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        cfg = {
            'service': 'credentials/list',
            'tests': [
                { #1
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'maxResults': 1 },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'credentialIDs' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': '<', 'arg': { 'credentialIDs': 2 } }
                    ]
                },
                { #2
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'maxResults': 5 },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'credentialIDs' ] },
                        { 'condition': 'not in', 'arg': [ 'error' ] },
                        { 'condition': '<', 'arg': { 'credentialIDs': 6 } }
                    ]
                },
                { #3
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
        r = self.generic_test(cfg)
        self.credential_IDs = self.list_utility(64)
        if len(self.credential_IDs) > 1:
            if len(self.list_utility(len(self.credential_IDs)/5 + 1, 5)) is len(self.credential_IDs):
                print '[', CSC.highlight('OK', 'green', bold=True), '] - credentials/list pagination test'
            else:
                print '[', CSC.highlight('KO', 'red', bold=True), '] - credentials/list pagination test'
        return self.credential_IDs

    def list_utility(self, max_results=1, iterations=-1):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        credentials_ids = []
        payload = { 'maxResults': max_results }
        dots_num = 0
        while iterations is not 0:
            r = requests.post(self.service_URLs['credentials/list'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
            if r.text is not None and str(r.text) != '':
                try:
                    j = r.json()
                except ValueError:
                    print CSC.highlight('Invalid json response', 'red', bold=True)
                    break
            else:
                print CSC.highlight('Invalid response', 'red', bold=True)
                break
            if 'error' in j:
                break
            elif 'credentialIDs' in j and isinstance(j['credentialIDs'], list):
                credentials_ids.extend([x.encode('utf-8') for x in j['credentialIDs']])
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
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'key>status', 'key>algo', 'key>len' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } }
                    ]
                },
                { #2
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'none' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'cert>certificates', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN', 'PIN', 'OTP' ] }
                    ]
                },
                { #3
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN', 'PIN', 'OTP' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } }
                    ]
                },
                { #4
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'chain' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo', 'PIN', 'OTP' ] },
                        { 'condition': '>', 'arg': { 'cert>certificates': 1 } }
                    ]
                },
                { #5
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single', 'certInfo': True },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } }
                    ]
                },
                { #6
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'single' },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'cert>certificates' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'PIN', 'OTP', 'cert>validFrom', 'cert>validTo', 'cert>subjectDN', 'cert>serialNumber', 'cert>issuerDN' ] },
                        { 'condition': '=', 'arg': { 'cert>certificates': 1 } }
                    ]
                },
                { #7
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': { 'credentialID': credential_id, 'certificates': 'chain', 'authInfo': True },
                    'exp_result': [
                        { 'condition': 'in' if auth_mode == 'explicit' else 'not in', 'arg': [ 'PIN', 'OTP' ] },
                        { 'condition': 'in', 'arg': [ 'cert>certificates' ] },
                        { 'condition': 'not in', 'arg': [ 'error', 'error_description', 'cert>validFrom', 'cert>validTo' ] },
                        { 'condition': '>', 'arg': { 'cert>certificates': 1 } }
                    ]
                }
            ]
        }
        self.generic_test(cfg)

    def get_credential_info(self, credential_id=None, print_details=False, certificates='none'):
        if credential_id is None:
            raise RuntimeError('*** Credential ID unavailable ***')
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')

        payload = {
            'certificates': certificates,
            'authInfo': True,
            'certInfo': True,
            'credentialID': credential_id
        }
        r = requests.post(self.service_URLs['credentials/info'], headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, verify=False, json=payload)
        j = r.json()
        if 'error' in j:
            raise RuntimeError('*** Unable to get credential info' + '' if 'error_description' not in j else (': ' + j['error_description']) + ' ***')
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

        if print_details:
            print CSC.highlight('Credential ID', bold=True), CSC.highlight(credential_id, 'green' if is_valid else 'red', bold=True)
            print json.dumps(j, indent=4, sort_keys=True)

        return is_valid, auth_mode, pin_presence, otp_presence, otp_type

    def send_otp(self, credential_id=None):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if credential_id is None:
            raise RuntimeError('*** Credential ID unavailable ***')
        cfg = {
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
        r = self.generic_test(cfg)
        for rr in r:
            if 'error' not in rr:
                print CSC.highlight('* OTP for credential ' + credential_id + ' sent', 'cyan')
                break

    def authorize_test(self, credential_id=None, auth_mode='explicit', pin_presence=True, pin=None, otp_presence=True, otp_type='online', num_signatures=20, is_valid=True):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if auth_mode == 'explicit' and pin is None:
            pin = getpass.getpass(CSC.highlight('Please enter the PIN value [press ENTER to abort]: ', bold=True))
            if pin == '':
                raise RuntimeError('*** Unable to perform Authorize tests: PIN is empty ***')
        elif auth_mode == 'explicit':
            tmp = getpass.getpass(CSC.highlight('Change default PIN [' + pin + ']: ', bold=True))
            if tmp != '':
                pin = tmp
        if auth_mode == 'explicit' and otp_presence:
            otp = raw_input(CSC.highlight('Please enter the OTP value [press ENTER to abort]: ', bold=True))
            if otp == '':
                raise RuntimeError('*** Unable to perform Authorize tests: OTP is empty ***')

        if is_valid:
            if auth_mode == 'explicit':
                wrong_pin_test_error = 'invalid_pin'
                wrong_pin_test_error_description = 'The PIN is invalid'
            else:
                wrong_pin_test_error = 'invalid_otp'
                wrong_pin_test_error_description = 'The OTP is invalid'
        else:
            wrong_pin_test_error = 'invalid_request'
            wrong_pin_test_error_description = 'Invalid certificate status'

        cfg = {
            'service': 'credentials/authorize',
            'tests': [
                { #2 - wrong PIN
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                        'PIN': '>>0'
                    },
                    'exp_result': [
                        { 'condition': 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'error': wrong_pin_test_error, 'error_description': wrong_pin_test_error_description } },
                    ]
                },
                { #3
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'credentialID': credential_id,
                        'numSignatures': num_signatures,
                    },
                    'exp_result': [
                        { 'condition': 'in' if is_valid else 'not in', 'arg': [ 'SAD' ] },
                        { 'condition': 'not in' if is_valid else 'in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }

        if auth_mode == 'explicit' and otp_presence:
            for i in cfg['tests']:
                i['input']['OTP'] = otp
            tmp = { #1 - wrong OTP
                'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                'input': {
                    'OTP': '>>0',
                    'credentialID': credential_id,
                    'numSignatures': num_signatures,
                },
                'exp_result': [
                    { 'condition': 'in', 'arg': [ 'error' ] },
                    { 'condition': 'not in', 'arg': [ 'SAD' ] },
                    { 'condition': 'eq', 'arg': { 'error': 'invalid_otp' if is_valid else 'invalid_request', 'error_description': 'The OTP is invalid' if is_valid else 'Invalid certificate status' } }
                ]
            }
            cfg['tests'].insert(0, tmp)

        if auth_mode == 'explicit' and pin_presence:
            for i in cfg['tests']:
                if 'PIN' not in i['input']:
                    i['input']['PIN'] = pin

        try:
            r = self.generic_test(cfg)
        except KeyboardInterrupt:
            print CSC.highlight('Authorization tests interrupted...skipping to next credential', 'yellow')
            return None
        self.SAD = None
        for i in xrange(len(cfg['tests']) - 1, -1, -1):
            if 'error' not in r[i] and 'SAD' in r[i]:
                self.SAD = r[i]['SAD']
                break
        if self.SAD is None:
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
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
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
        r = self.generic_test(cfg)
        for i in xrange(len(cfg['tests']) - 1, -1, -1):
            if 'error' not in r[i] and 'SAD' in r[i]:
                self.SAD = r[i]['SAD']
                break
        return self.SAD

    def sign_hash_test(self, sad=None, credential_id=None):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        if sad is None:
            raise RuntimeError('*** SAD unavailable ***')
        #TODO add tests based on the supported sign algorithms
        cfg = {
            'service': 'signatures/signHash',
            'tests': [
                { #1
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        'signAlgo': '1.2.840.113549.1.1.11', #ALGO_SHA256_WITH_RSA_ENC
                        #'hashAlgo': '2.16.840.1.101.3.4.2.1',
                        #echo "abc" | sha256sum | awk '{ print $1 }' | tr -d '\r\n' | xxd -r -p | base64 | tr -d '\r\n'
                        'hash': [ 'XfzjKkvpFPHCMXbOySVUWJ2x4wMsIrJysfHWloHOwRM=' ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 1 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #2
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        'signAlgo': '1.2.840.113549.1.1.13', #ALGO_SHA512_WITH_RSA_ENC
                        #'hashAlgo': '2.16.840.1.101.3.4.2.1',
                        'hash': [
                            #echo "abc" | sha512sum | awk '{ print $1 }' | tr -d '\r\n' | xxd -r -p | base64 | tr -d '\r\n'
                            'TyhdDAzHcobYcxeYt6riY54oJw1BZvQNdpy73KUjBxTYSEg9Nk4vOf5suQg8FSKbOaM2FevG1XYF98Q/aQZznQ==',
                            'TyhdDAzHcobYcxeYt6riY54oJw1BZvQNdpy73KUjBxTYSEg9Nk4vOf5suQg8FSKbOaM2FevG1XYF98Q/aQZznQ=='
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 2 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #3
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        #'signAlgo': '1.2.840.113549.1.1.12', #ALGO_SHA384_WITH_RSA_ENC
                        'signAlgo': '1.2.840.113549.1.1.1', #ALGO_RSA_ENC
                        'hashAlgo': '2.16.840.1.101.3.4.2.2', #HASH_SHA384_OID
                        'hash': [
                            '6NFCC0/0HD8SGG2JSpnhxKpoHaecRwB+na3s2eywSC7h4iRRDnSEB4wCifNDlrnD',
                            '6NFCC0/0HD8SGG2JSpnhxKpoHaecRwB+na3s2eywSC7h4iRRDnSEB4wCifNDlrnD',
                            '6NFCC0/0HD8SGG2JSpnhxKpoHaecRwB+na3s2eywSC7h4iRRDnSEB4wCifNDlrnD'
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 3 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #4 - Invalid digest value length
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        'signAlgo': '1.2.840.113549.1.1.13', #ALGO_SHA512_WITH_RSA_ENC
                        'hash': [
                            '6NFCC0/0HD8SGG2JSpnhxKpoHaecRwB+na3s2eywSC7h4iRRDnSEB4wCifNDlrnD'
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'error' ] },
                        { 'condition': 'eq', 'arg': { 'error_description': 'Invalid digest value length' } },
                        { 'condition': 'not in', 'arg': [ 'signatures' ] }
                    ]
                },
                { #5
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        #'signAlgo': '1.2.840.113549.1.1.5', #ALGO_SHA1_WITH_RSA_ENC
                        'signAlgo': '1.2.840.113549.1.1.1', #ALGO_RSA_ENC
                        'hashAlgo': '1.3.14.3.2.26', #HASH_SHA1_OID
                        'hash': [
                            '6YKdreWGdpJyq4BjtMWYHntoTbE=',
                            '6YKdreWGdpJyq4BjtMWYHntoTbE=',
                            '6YKdreWGdpJyq4BjtMWYHntoTbE=',
                            '6YKdreWGdpJyq4BjtMWYHntoTbE='
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 4 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #6
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,

                        'signAlgo': '1.2.840.113549.1.1.14', #ALGO_SHA224_WITH_RSA_ENC
                        #'signAlgo': '1.2.840.113549.1.1.1', #ALGO_RSA_ENC
                        #'hashAlgo': '2.16.840.1.101.3.4.2.4', #HASH_SHA224_OID
                        'hash': [
                            'HR+POhJA2jWq5MiRp3/qEQz/Svxpi1ihA9GmSw==',
                            'HR+POhJA2jWq5MiRp3/qEQz/Svxpi1ihA9GmSw==',
                            'HR+POhJA2jWq5MiRp3/qEQz/Svxpi1ihA9GmSw=='
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 3 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                },
                { #7
                    'headers': { 'Authorization' : 'Bearer ' + self.session_key },
                    'input': {
                        'SAD': sad,
                        'signAlgoParams': 'MDmgDzANBglghkgBZQMEAgEFAKEcMBoGCSqGSIb3DQEBCDANBglghkgBZQMEAgEFAKIDAgEgowMCAQE=',
                        'signAlgo': '1.2.840.113549.1.1.10', #RSASSA-PSS
                        'hash': [
                            'XfzjKkvpFPHCMXbOySVUWJ2x4wMsIrJysfHWloHOwRM=',
                            'XfzjKkvpFPHCMXbOySVUWJ2x4wMsIrJysfHWloHOwRM=',
                            'XfzjKkvpFPHCMXbOySVUWJ2x4wMsIrJysfHWloHOwRM='
                        ],

                        'credentialID': credential_id
                    },
                    'exp_result': [
                        { 'condition': 'in', 'arg': [ 'signatures' ] },
                        { 'condition': '=', 'arg': { 'signatures': 3 } },
                        { 'condition': 'not in', 'arg': [ 'error' ] }
                    ]
                }
            ]
        }
        self.generic_test(cfg)

    def timestamp_test(self):
        if self.session_key is None:
            raise RuntimeError('*** Session key unavailable ***')
        cfg = {
            'service': 'signatures/timestamp',
            'tests': [
                { #1
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
        self.generic_test(cfg)

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
        self.generic_test(cfg)

    def revoke(self, s):
        #REVOKE Test 1
        payload = {
            'token': s
        }
        print CSC.highlight('Revoking token ' + s + ' ...', bold=True)
        requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        payload = {
            'hash': 'uB28DAYaAZ+74aWHm30uDgeVB18=',
            'hashAlgo': '1.3.14.3.2.26'
        }
        r = requests.post(self.service_URLs['signatures/timestamp'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        j = r.json()
        if 'error' in j:
            CSC.printOKmsg('auth/revoke', 1)
        else:
            CSC.printKOmsg('Revoke', 1, payload, j)
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
                print CSC.highlight('Revoking token ' + refreshToken + ' ...', bold=True)
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    payload = {
                        'refresh_token': refreshToken
                    }
                    r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
                    j = r.json()
                    if 'error' in j:
                        CSC.printOKmsg('auth/revoke', 2)
                    else:
                        CSC.printKOmsg('Revoke', 2, payload, j)
                else:
                    print CSC.highlight(json.dumps(r.json(), indent=4, sort_keys=True), 'red')
                    print CSC.highlight('*** Unable to perfom revoke test 2: revoke failed', 'red')
                    print
            else:
                print CSC.highlight('*** Unable to perfom revoke test 2: login failed', 'red')
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
                print CSC.highlight('Revoking token ' + refreshToken + ' ...', bold=True)
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    payload = {
                        'refresh_token': refreshToken
                    }
                    r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded }, json=payload)
                    j = r.json()
                    if 'error' in j:
                        CSC.printOKmsg('auth/revoke', 3)
                    else:
                        CSC.printKOmsg('Revoke', 3, payload, j)
                else:
                    j = r.json()
                    print CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red')
                    print CSC.highlight('*** Unable to perfom revoke test 3: revoke failed', 'red')
                    print
            else:
                print CSC.highlight('*** Unable to perfom revoke test 3: login failed', 'red')
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
                print CSC.highlight('Revoking token ' + sessionKey + ' ...', bold=True)
                r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sessionKey }, json=payload)
                if r.text == '' or 'error' not in r.json():
                    r = requests.get(self.service_URLs['credentials/list'], verify=False, headers={'Authorization': 'Bearer ' + sessionKey})
                    j = r.json()
                    if 'error' in j:
                        CSC.printOKmsg('auth/revoke', 4)
                    else:
                        CSC.printKOmsg('Revoke', 4, payload, j)
                else:
                    j = r.json()
                    print CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red')
                    print CSC.highlight('*** Unable to perfom revoke test 4: revoke failed', 'red')
                    print
            else:
                print CSC.highlight('*** Unable to perfom revoke test 4: login failed', 'red')

    def single_revoke(self, token):
        if token is None or token == '':
            print CSC('Cannot revoke empty token', 'yellow')
            return
        payload = {
            'token': token
        }
        print CSC.highlight('Revoking token ' + token + ' ...', bold=True)
        r = requests.post(self.service_URLs['auth/revoke'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.session_key }, json=payload)
        if r.text != '' and 'error' in r.json():
            j = r.json()
            print CSC.highlight('\n<=', bold=True), CSC.highlight(json.dumps(j, indent=4, sort_keys=True), 'red')
            print CSC.highlight('*** Unable to revoke sessionKey ' + token + ' ***\n', 'red', bold=True)
            print

    @staticmethod
    def printOKmsg(service, testNum):
        print '[', CSC.highlight('OK', 'green', bold=True), '] -', service, 'test', testNum

    @staticmethod
    def printKOmsg(service, testNum, request, response):
        print CSC.highlight('\n =>', bold=True), CSC.highlight(json.dumps(request, indent=4, sort_keys=True), 'red')
        print CSC.highlight('\n <=', bold=True), CSC.highlight(json.dumps(response, indent=4, sort_keys=True), 'red')
        print '[', CSC.highlight('KO', 'red', bold=True), '] -', service, 'test', testNum, '\n'

    @staticmethod
    def highlight(msg, color='white', bold=False, underline=False):
        if not sys.stdout.isatty():
            return msg
        attr = []
        if bold:
            attr.append('1')
        elif underline:
            attr.append('4')
        else:
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
                'white':  '97'
            }[color]
        except KeyError:
            #default to white
            color = '97'
        attr.append(color)
        return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), msg)

    def sig_handler(self, signal, frame):
        signame = {
            2:  'SIGINT',
            15: 'SIGTERM'
        }[signal]
        print CSC.highlight('\n*** ' + signame + ' detected ***', 'yellow', bold=True)
        if self.SAD is not None and self.SAD != '':
            self.single_revoke(self.SAD)
        if self.session_key is not None and self.session_key != '':
            do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            while not re.match('[yYnN]', do_revoke):
                if do_revoke == '':
                    do_revoke = 'y'
                    break
                do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
            if re.match('[yY]', do_revoke):
                self.single_revoke(self.session_key)
        sys.exit(1)

    def ask_and_revoke(self, exit=False, session_key=None):
        do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        while not re.match('[yYnN]', do_revoke):
            if do_revoke == '':
                do_revoke = 'y'
                break
            do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        if re.match('[yY]', do_revoke):
            self.single_revoke(self.session_key if session_key is None else session_key)
        if exit:
            sys.exit(1)

    def global_test(self):
        self.info_test()
        self.generic_errors()
        login_executed = False
        if self.session_key is None or self.session_key == '':
            login_executed = True
            try:
                self.login_test()
            except RuntimeError as e:
                print CSC.highlight(e, 'red', bold=True)
                sys.exit(1)
        print CSC.highlight('Using session key ' + self.session_key, 'yellow')
        self.timestamp_test()
        self.list_test()
        print CSC.highlight(str(len(self.credential_IDs)) + ' credential' + ('' if len(self.credential_IDs) == 1 else 's') + ' found', bold=True)
        print CSC.highlight('Credentials IDs:', bold=True), CSC.highlight(json.dumps(self.credential_IDs, indent=4, sort_keys=True), 'cyan')
        if self.test_credentials and len(self.credential_IDs) > 0:
            for c in self.credential_IDs:
                print CSC.highlight('Testing', bold=True),
                try:
                    is_valid, auth_mode, pin_presence, otp_presence, otp_type = self.get_credential_info(credential_id=c, print_details=True)
                    self.credentials_info_test(c, auth_mode)
                    if is_valid or self.test_invalid_credentials:
                        abort_signature = False
                        if auth_mode == 'implicit' or (auth_mode == 'explicit' and otp_presence and otp_type == 'online'):
                            r = ''
                            if not login_executed or 'barelli' not in self.username:
                                while r != 'y' and r != 'n':
                                    r = raw_input(CSC.highlight('WARNING! Username could not belong to Davide Barelli. Continue? [y/n] ', 'yellow', bold=True))
                                if r != 'y':
                                    abort_signature = True
                        if not abort_signature and auth_mode == 'implicit':
                            r = ''
                            while r != 'y' and r != 'n':
                                r = raw_input(CSC.highlight('Implicit credential, do you want to continue? [y/n] ', 'yellow', bold=True))
                            if r != 'y':
                                abort_signature = True
                        elif not abort_signature and auth_mode == 'explicit' and otp_presence and otp_type == 'online':
                            self.send_otp(c)

                        if not abort_signature:
                            self.authorize_test(c, auth_mode, pin_presence, self.PIN, otp_presence, otp_type, 20, is_valid)
                            self.extend_test(self.SAD, c)
                            self.sign_hash_test(self.SAD, c)
                    else:
                        print CSC.highlight('*** SKIP: invalid credential ***', 'yellow')
                except RuntimeError as e:
                    print CSC.highlight(e, 'yellow', bold=True)
        elif not self.test_credentials:
            print CSC.highlight('*** SKIPPING CREDENTIALS TESTS ***', 'yellow')
        else:
            print CSC.highlight('*** No credentials found! ***', 'yellow')

        do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        while not re.match('[yYnN]', do_revoke):
            if do_revoke == '':
                do_revoke = 'y'
                break
            do_revoke = raw_input(CSC.highlight('Revoke session key? [Y/n] ', bold=True))
        if re.match('[yY]', do_revoke):
            self.revoke(self.refresh_token if self.refresh_token is not None else self.session_key)

    def scan(self):
        if self.session_key is None:
            r = requests.post(self.service_URLs['auth/login'], verify=False, headers={ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.credential_encoded })
            if r.text is not None and str(r.text) != '':
                try:
                    j = r.json()
                except ValueError:
                    self.single_revoke(self.session_key)
                    print CSC.highlight('Invalid json response', 'red', bold=True)
                    return
            else:
                self.single_revoke(self.session_key)
                print CSC.highlight('Invalid response', 'red', bold=True)
                return

            if 'error' in j or 'access_token' not in j:
                print CSC.highlight('An error occurred', 'red', bold=True)
                print CSC.highlight(json.dumps(r.json(), indent=4, sort_keys=True), 'red')
                return

            self.session_key = j['access_token']
        print CSC.highlight('Using session key ' + self.session_key, 'yellow')
        credentials_ids = self.list_utility(64)
        if len(credentials_ids) > 0:
            print CSC.highlight(str(len(credentials_ids)) + ' credential' + ('' if len(credentials_ids) == 1 else 's') + ' found', bold=True)
            print CSC.highlight('Credentials IDs:', bold=True), CSC.highlight(json.dumps(credentials_ids, indent=4, sort_keys=True), 'cyan')
            for c in credentials_ids:
                try:
                    self.get_credential_info(credential_id=c, print_details=True, certificates='single')
                except RuntimeError as e:
                    print CSC.highlight('An error occurred while getting info for credential ' + c + ' - ' + str(e), 'red', bold=True)
        else:
            print CSC.highlight('No credential found', 'red', bold=True)
        self.ask_and_revoke()

    @staticmethod
    def check_logos():
        p = re.compile("^.+\.([^.]+)$")
        print CSC.highlight('Checking service logos', bold=True)
        content_types = {
            "jpeg": "image/jpeg",
            "jpg":  "image/jpeg",
            "png":  "image/png"
        }
        for k, v in CSC.service_logo_URLs.items():
            try:
                m = p.search(v)
                r = requests.get(v)
                if r is None:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('info response is empty', color='yellow')
                elif r.status_code != 200:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('status_code ' + str(r.status_code), color='yellow')
                elif m.group(1) in content_types and r.headers['content-type'] != content_types[m.group(1)]:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('content-type ' + r.headers['content-type'], color='yellow')
                elif m.group(1) not in content_types:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('Unable to check content-type ' + r.headers['content-type'], color='yellow')
                else:
                    print '[', CSC.highlight('OK', color='green', bold=True), '] -', CSC.highlight(k, underline=True), 'URL [', v, ']'
            except Exception as e:
                print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('an exception has been thrown', color='yellow')
                print e

        print CSC.highlight('\nChecking OAuth logos', bold=True)
        for k, v in CSC.oauth_logo_URLs.items():
            try:
                m = p.search(v)
                r = requests.get(v, allow_redirects=False)
                if r is None:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('info response is empty', color='yellow')
                elif r.status_code != 200:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('status_code ' + str(r.status_code), color='yellow')
                elif m.group(1) in content_types and r.headers['content-type'] != content_types[m.group(1)]:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('content-type ' + r.headers['content-type'], color='yellow')
                elif m.group(1) not in content_types:
                    print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('Unable to check content-type ' + r.headers['content-type'], color='yellow')
                else:
                    print '[', CSC.highlight('OK', color='green', bold=True), '] -', CSC.highlight(k, underline=True), 'URL [', v, ']'
            except Exception as e:
                print '[', CSC.highlight('KO', color='red', bold=True), '] - Logo test', CSC.highlight(k, color='cyan'), 'failed for URL [', v, ']:', CSC.highlight('an exception has been thrown', color='yellow')
                print e

    def __init__(self, user=None, passw='password', pin='12345678', env=None, context=None, session_key=None, verbose=True):
        #ctx = ssl.create_default_context()
        #ctx.check_hostname = False
        #ctx.verify_mode = ssl.CERT_NONE
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

        self.credential_encoded = None if not user else base64.b64encode('{}:{}'.format(self.username, passw))
        self.session_key = session_key
        self.refresh_token = None
        self.PIN = pin
        self.SAD = None

        if verbose:
            CSC.tool_info()
            print CSC.highlight('Using endpoint:', bold=True), CSC.highlight(context, underline=True)
            if self.username is not None:
                print CSC.highlight('Using account:', bold=True), CSC.highlight(self.username, 'cyan')
            if self.credential_encoded is not None:
                print CSC.highlight('Using authorization header:', bold=True), self.credential_encoded
            print '\n###\n'

        signal.signal(signal.SIGINT, self.sig_handler)
        signal.signal(signal.SIGTERM, self.sig_handler)

        if 'https' in context:
            try:
                requests.packages.urllib3.disable_warnings()
            except:
                print CSC.highlight('Unable to disable urlib3 warnings', 'yellow')
                print CSC.highlight('Update `requests` module or execute `export PYTHONWARNINGS="ignore:Unverified HTTPS request"` to suppress HTTPS warnings', 'yellow')

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'logo':
        CSC.check_logos()
        sys.exit(0)

    m = CSCCursesMenu('credentials.json')
    try:
        data = m.display()
    except curses.error:
        m.destroy()
        print CSC.highlight('An error occurred: please increase window size', 'red', bold=True)
        sys.exit(1)
    except Exception as e:
        m.destroy()
        traceback.print_exc()
        sys.exit(1)
    finally:
        if not curses.isendwin():
            m.destroy()
    if not data:
        sys.exit(0)

    t = CSC(data['username'], data['password'], context=data['ctx_path'], session_key=data['session_key'])
    if len(sys.argv) > 1 and sys.argv[1] == 'scan':
        t.scan()
    else:
        t.global_test()


