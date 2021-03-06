#!/usr/bin/python
#
# Copyright 2011 Alberto Milone <albertomilone@gmail.com>
#
# Author: Alberto Milone <albertomilone@gmail.com>
#
# This program is largely based on applet.py from the Hamster project.
#
#
# This program is free software: you can redistribute it and/or modify it 
# under the terms of either or both of the following licenses:
#
# 1) the GNU Lesser General Public License version 3, as published by the 
# Free Software Foundation; and/or
# 2) the GNU Lesser General Public License version 2.1, as published by 
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the applicable version of the GNU Lesser General Public 
# License for more details.
#
# You should have received a copy of both the GNU Lesser General Public 
# License version 3 and version 2.1 along with this program.  If not, see 
# <http://www.gnu.org/licenses/>
#

import gobject
import gtk
import appindicator

import logging
import datetime as dt

import pygtk
pygtk.require("2.0")



import dbus, dbus.service, dbus.mainloop.glib
import locale

from hamster.configuration import conf, runtime, dialogs

from hamster import stuff, client

# controllers for other windows
from hamster import widgets
from hamster import idle
from hamster.applet import HamsterApplet

import pango

try:
    import wnck
except:
    logging.warning("Could not import wnck - workspace tracking will be disabled")
    wnck = None

try:
    import pynotify
    pynotify.init('Hamster Applet')
except:
    logging.warning("Could not import pynotify - notifications will be disabled")
    pynotify = None



class FakeApplet(object):
    '''Fake Applet class to trick HamsterApplet'''

    def __init__(self):
        pass

    def add(self, *args):
        pass

    def setup_menu_from_file(self, *args):
        pass


class HamsterIndicator(HamsterApplet):
    
    def __init__(self, applet=None):
        # Create a fake applet since HamsterApplet requires one
        applet = FakeApplet()
        self.storage = client.Storage()
        
        self.prev_activity_menuitems = [] #holds the list of previous activity menu items
        
        self.indicator = appindicator.Indicator ("hamster-applet",
                                  "hamster-applet",#"file-manager",
                                  appindicator.CATEGORY_SYSTEM_SERVICES)
        self.indicator.set_status (appindicator.STATUS_ACTIVE)
        self.indicator.set_label("")
        
        #timer
        self.activity, self.duration = None, None        
        
        self.menu = gtk.Menu()

        self.activity_item = gtk.MenuItem("")
        self.menu.append(self.activity_item)
        # this is where you would connect your menu item up with a function:
        self.activity_item.connect("activate", self.on_new_activity_activated, None)
        self.activity_label = self.activity_item.get_child()
        self.activity_label.connect('style-set', self.on_label_style_set)

        # show the items
        self.activity_item.show()

        self.stop_activity_item = gtk.MenuItem(_(u"Sto_p Tracking"))
        self.menu.append(self.stop_activity_item)
        # this is where you would connect your menu item up with a function:
        self.stop_activity_item.connect("activate", self.on_stop_activity_activated, None)
        # show the items
        self.stop_activity_item.show()

        self.append_separator(self.menu)

        self.earlier_activity_item = gtk.MenuItem(_(u"Add earlier activity"))
        self.menu.append(self.earlier_activity_item)
        # this is where you would connect your menu item up with a function:
        self.earlier_activity_item.connect("activate", self.on_earlier_activity_activated, None)
        # show the items
        self.earlier_activity_item.show()

        self.overview_show_item = gtk.MenuItem(_(u"Show _Overview"))
        self.menu.append(self.overview_show_item)
        # this is where you would connect your menu item up with a function:
        self.overview_show_item.connect("activate", self.on_overview_show_activated, None)
        # show the items
        self.overview_show_item.show()

        self.append_separator(self.menu)

        self.preferences_show_item = gtk.MenuItem(_(u"Preferences"))
        self.menu.append(self.preferences_show_item)
        # this is where you would connect your menu item up with a function:
        self.preferences_show_item.connect("activate", self.on_show_preferences_activated, None)
        # show the items
        self.preferences_show_item.show()

        self.append_separator(self.menu)

        self.quit_item = gtk.MenuItem(_(u"_Quit"))
        self.menu.append(self.quit_item)
        # this is where you would connect your menu item up with a function:
        self.quit_item.connect("activate", gtk.main_quit, None)
        # show the items
        self.quit_item.show()


        # Call constructor after the gtk.Menu is ready
        super(HamsterIndicator, self).__init__(applet)

        # Hide the panel button since it's not supported
        self.button.hide()

        #self.window.set_title(_(u"Time Tracker"))

        # Add a window decoration
        #self.window.set_decorated(True)

        # Place the window near the mouse cursor
        self.window.set_position(gtk.WIN_POS_MOUSE)

        # Do not skip the taskbar
        self.window.set_skip_taskbar_hint(True)

        # Do not skip the pager
        self.window.set_skip_pager_hint(True)
    
    def update_header(self):
        if self.last_activity and self.last_activity['end_time'] is None:            
            if self.duration:
              label = "%s %s" % (self.shorten_activity_text(self.activity), self.duration)
            self.indicator.set_label(label)
        else:
            self.indicator.set_label("No activity")
    
    def on_new_activity_activated(self, *args):
        self.show_dialog()

    def on_stop_activity_activated(self, *args):
        runtime.storage.stop_tracking()
        self.last_activity = None

    def on_show_preferences_activated(self, *args):
        dialogs.prefs.show(self.indicator)

    def on_overview_show_activated(self, *args):
        dialogs.overview.show(self.indicator)

    def on_earlier_activity_activated(self, *args):
        dialogs.edit.show(self.indicator)

    def refresh_menu(self):
        '''Update the menu so that the new activity text is visible'''
        self.indicator.set_menu(self.menu)

    def reformat_label(self):
        '''This adds a method which belongs to hamster.applet.PanelButton'''
        label = self.activity
        if self.duration:
            label = "%s %s" % (self.shorten_activity_text(self.activity), self.duration)
 
        label = '<span gravity="south">%s</span>' % label
        
        if self.activity_label:
            self.activity_label.set_markup("") #clear - seems to fix the warning
            self.activity_label.set_markup(label)

    def on_label_style_set(self, widget, something):
        self.reformat_label()

    def append_separator(self, menu):
        '''Add separator to the menu'''
        separator = gtk.SeparatorMenuItem()
        separator.show()
        menu.append(separator)

    def update_label(self):
        '''Override for menu items sensitivity and to update the menu'''
        if self.last_activity and self.last_activity['end_time'] is None:
            self.stop_activity_item.set_sensitive(1)
            
            delta = dt.datetime.now() - self.last_activity['start_time']
            duration = delta.seconds /  60            
            label = "%s %s" % (self.last_activity['name'],
                               stuff.format_duration(duration, False))
            self.set_activity_text(self.last_activity['name'],
                                 stuff.format_duration(duration, False))
        else:
            self.stop_activity_item.set_sensitive(0)
            label = "%s" % _(u"New activity")#_(u"No activity")            
            self.set_activity_text(label, None)
        
        self.update_header()
        
        # Update the menu or the new activity text won't show up
        self.refresh_menu()
        
        self.update_prev()
    
    def update_prev(self):
        '''Updates the list of previous activities, shows last 5 activities'''
        num_prev = len(self.prev_activity_menuitems)
        for item in self.prev_activity_menuitems:
            
            self.menu.remove(item)
        if num_prev>0:
            self.menu.remove(self.prev_separator)
            
        facts = self.storage.get_todays_facts()
        facts.sort(key = lambda x: x['start_time'])
        facts.reverse()
        
        self.prev_activity_menuitems = []
        names = set()
        i = 3
        for fact in facts:
            if i -3 > 5:
                break
            
            if fact["name"] in names:
                continue
            
            names.add(fact["name"])
            item = gtk.MenuItem(self.shorten_activity_text(fact["name"]))
            item.fact = fact
            item.connect("activate",self.on_prev_activity_activated)
            item.show()
            self.menu.insert(item,i)
            self.prev_activity_menuitems.append(item)
            i+=1
        
        if len(facts)>0:
            self.prev_separator = gtk.SeparatorMenuItem()
            self.menu.insert(self.prev_separator,i)
            self.prev_separator.show()
    
    def on_prev_activity_activated(self, *args):
        '''When a previous activity's menu item is clicked'''
        fact = args[0].fact
        tags = ",".join([x for x in fact["tags"]])
        self.storage.add_fact(str(fact["name"]) , tags=tags, category_name=str(fact["category"]), description=str(fact["description"]))
        
    def position_popup(self):
        '''Override the superclass method and do nothing'''
        pass

    def on_window_size_request(self, *args):
        '''Override the superclass method and do nothing'''
        pass

    def set_last_activity(self):
        '''Override to change the Stop button sensitivity'''
        #self.stop_activity_item.set_sensitive(self.last_activity != None)
        super(HamsterIndicator, self).set_last_activity()

    def on_stop_tracking_clicked(self, widget):
        '''Override to make the Stop button insensitive'''
        self.stop_activity_item.set_sensitive(0)
        super(HamsterIndicator, self).on_stop_tracking_clicked(widget)

    def on_switch_activity_clicked(self, widget):
        '''Override to make the Stop button sensitive'''
        self.stop_activity_item.set_sensitive(1)
        super(HamsterIndicator, self).on_switch_activity_clicked(widget)

    def set_activity_text(self, activity, duration):
        '''This adds a method which belongs to hamster.applet.PanelButton'''        
        self.activity = activity
        self.duration = duration
        self.reformat_label()
    
    def shorten_activity_text(self, activity):
        activity = stuff.escape_pango(activity)
        if len(activity) > 25:  #ellipsize at some random length
            activity = "%s%s" % (activity[:25], "...")
        return activity
        
    def show_dialog(self, is_active=True):
        """Show new task window"""
        self.button.set_active(is_active)

        if is_active == False:
            self.window.hide()
            return True

#        # doing unstick / stick here, because sometimes while switching
#        # between workplaces window still manages to disappear
        self.window.unstick()
        self.window.stick() #show on all desktops

        self.new_name.set_text("");
        self.new_tags.set_text("");
        gobject.idle_add(self._delayed_display)

def start_indicator():
    from hamster import i18n
    i18n.setup_i18n()
    hamster_indicator = HamsterIndicator()
    gtk.main()
    
if __name__ == "__main__":
    start_indicator()
