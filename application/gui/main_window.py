#!/usr/bin/env python

import os
import sys
import gtk
import pango
import webbrowser
import locale
import user

from menus import MenuManager
from input_dialog import InputDialog, AddBookmarkDialog

from ConfigParser import RawConfigParser

# gui imports
from about_window import AboutWindow
from options_window import OptionsWindow
from icons import IconManager
from associations import AssociationManager
from indicator import Indicator

# plugin imports
# TODO: Load plugins dynamically
from plugins import *

class MainWindow(gtk.Window):
	"""Main application class"""

	# version
	version = '0.1a'
	build_number = '13'

	def __init__(self):
		# create main window and other widgets
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		self.realize()

		# create managers early
		self.icon_manager = IconManager(self)
		self.menu_manager = MenuManager(self)
		self.associations_manager = AssociationManager()

		self.set_title('Sunflower')
		
		if self.icon_manager.has_icon('sunflower'):
			# in case theme has its own icon, use that one
			self.set_icon_name('sunflower')
			
		else:
			self.set_icon_from_file(os.path.join(
										os.path.dirname(sys.argv[0]),
										'images',
										'sunflower_hi-def_64x64.png'
									))

		# set locale for international number formatting
		locale.setlocale(locale.LC_ALL)
	
		# config parsers
		self.options = None 
		self.tab_options = None 
		self.bookmark_options = None
		self.toolbar_options = None
		
		# popup menus
		self.menu_bookmarks = None
		self.menu_mounts = None
		
		# location of all configuration files
		self.config_path = None
		
		self.clipboard = gtk.Clipboard()
	
		# load config
		self.load_config()

		if self.options.getboolean('main', 'hide_on_close'):
			self.connect("delete-event", self._delete_event)
		else:
			self.connect("delete-event", self._destroy)

		# create other guis
		self.indicator = Indicator(self)
		self.about_window = AboutWindow(self)
		self.options_window = OptionsWindow(self)

		# define local variables
		self._in_fullscreen = False

		# create menu items
		menu_bar = gtk.MenuBar()

		menu_items = (
			{
				'label': 'File',
				'submenu': (
					{
						'label': 'Test dialog',
						'callback': self.test
					},
					{
						'label': 'E_xit',
						'type': 'image',
						'stock': gtk.STOCK_QUIT,
						'callback' : self._destroy,
						'path': '<Sunflower>/File/Exit',
					},
				)
			},
			{
				'label': 'Mark',
				'submenu': (
					{
						'label': '_Select all',
						'type': 'image',
						'stock': gtk.STOCK_SELECT_ALL,
						'callback': self.select_all,
						'path': '<Sunflower>/Mark/SelectAll',
					},
					{
						'label': '_Unselect all',
						'callback': self.unselect_all,
						'path': '<Sunflower>/Mark/UnselectAll',
					},
					{
						'label': 'Invert select_ion',
						'callback': self.invert_selection,
						'path': '<Sunflower>/Mark/InvertSelection',
					},
					{'type': 'separator'},
					{
						'label': 'S_elect with pattern',
						'callback': self.select_with_pattern,
						'path': '<Sunflower>/Mark/SelectPattern',
					},
					{
						'label': 'Unselect with pa_ttern',
						'callback': self.unselect_with_pattern,
						'path': '<Sunflower>/Mark/UnselectPattern',
					},
					{'type': 'separator'},
					{
						'label': 'Compare _directories',
						'type': 'image',
						'stock': gtk.STOCK_DIRECTORY,
						'path': '<Sunflower>/Mark/Compare',
					}
				)
			},
			{
				'label': 'Settings',
				'submenu': (
					{
						'label': 'Show _hidden files',
						'type': 'checkbox',
						'active': self.options.getboolean('main', 'show_hidden'),
						'callback': self._toggle_show_hidden_files,
						'name': 'show_hidden_files',
						'path': '<Sunflower>/Settings/ShowHidden',
					},
					{
						'label': 'Show _toolbar',
						'type': 'checkbox',
						'active': self.options.getboolean('main', 'show_toolbar'),
						'callback': self._toggle_show_toolbar,
						'name': 'show_toolbar',
						'path': '<Sunflower>/Settings/ShowToolbar',
					},
					{
						'label': 'Show _command bar',
						'type': 'checkbox',
						'active': self.options.getboolean('main', 'show_command_bar'),
						'callback': self._toggle_show_command_bar,
						'name': 'show_command_bar',
						'path': '<Sunflower>/Settings/ShowCommandBar',
					},
					{'type': 'separator'},
					{
						'label': '_Options', 'type': 'image',
						'stock': gtk.STOCK_PREFERENCES,
						'callback': self.options_window._show,
						'path': '<Sunflower>/Settings/Options',
					},
				)
			},
			{
				'label': 'Tools',
			},
			{
				'label': 'Help',
				'right': True,
				'submenu': (
					{
						'label': '_Home page',
						'type': 'image',
						'stock': gtk.STOCK_HOME,
						'callback': self.goto_web,
						'data': 'rcf-group.com',
						'path': '<Sunflower>/Help/HomePage',
					},
					{'type': 'separator'},
					{
						'label': 'File a _bug report',
						'callback': self.goto_web,
						'data': 'code.google.com/p/sunflower-fm/issues/entry',
						'path': '<Sunflower>/Help/BugReport',
					},
					{
						'label': 'Check for _updates',
						'path': '<Sunflower>/Help/CheckForUpdates',
					},
					{'type': 'separator'},
					{
						'label': '_About',
						'type': 'image',
						'stock': gtk.STOCK_ABOUT,
						'callback': self.about_window._show,
						'path': '<Sunflower>/Help/About',
					}
				)
			},
		)

		# add items to main menu
		for item in menu_items:
			menu_bar.append(self.menu_manager.create_menu_item(item))
			
		# operations menu
		self.menu_operations = gtk.Menu()

		self._menu_item_operations = gtk.MenuItem(label='Operations')
		self._menu_item_operations.set_sensitive(False)
		self._menu_item_operations.set_submenu(self.menu_operations)
		
		menu_bar.insert(self._menu_item_operations, len(menu_items)-1)
		self._operations_visible = 0
			
		# load accelerator map
		self.load_accel_map(os.path.join(self.config_path, 'accel_map'))

		# create toolbar
		self.toolbar = gtk.Toolbar()
		self.toolbar.set_property(
						'no-show-all',
						not self.options.getboolean('main', 'show_toolbar')
					)

		# create notebooks
		hbox = gtk.HBox(True, 3)

		self.left_notebook = gtk.Notebook()
		self.left_notebook.set_scrollable(True)
		self.left_notebook.connect('focus-in-event', self._transfer_focus)
		self.left_notebook.connect('page-added', self._tab_moved)
		self.left_notebook.set_group_id(0)

		self.right_notebook = gtk.Notebook()
		self.right_notebook.set_scrollable(True)
		self.right_notebook.connect('focus-in-event', self._transfer_focus)
		self.right_notebook.connect('page-added', self._tab_moved)
		self.right_notebook.set_group_id(0)

		hbox.pack_start(self.left_notebook, True, True, 0)
		hbox.pack_start(self.right_notebook, True, True, 0)

		# command line prompt
		hbox2 = gtk.HBox(False, 0)

		self.path_label = gtk.Label()
		self.path_label.set_alignment(1, 0.5)
		self.path_label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

		# create history list
		self.command_list = gtk.ListStore(str)

		# create autocomplete entry
		self.command_completion = gtk.EntryCompletion()
		self.command_completion.set_model(self.command_list)
		self.command_completion.set_minimum_key_length(2)
		self.command_completion.set_text_column(0)

		# create editor
		self.command_edit = gtk.Entry()
		self.command_edit.set_completion(self.command_completion)
		self.command_edit.connect('activate', self.execute_command)
		self.command_edit.connect('key-press-event', self._command_edit_key_press)

		# load history file
		self._load_history()

		hbox2.pack_start(self.path_label, True, True, 3)
		hbox2.pack_start(self.command_edit, True, True, 0)

		# command buttons bar
		self.command_bar = gtk.HBox(True, 0)

		buttons = (
				('Refresh', 'Reload active item list (CTRL+R)', self._command_reload),
				('View', 'View selected file (F3)', None),
				('Edit', 'Edit selected file (F4)', self._command_edit),
				('Copy', 'Copy selected items from active to opposite list (F5)', self._command_copy),
				('Move', 'Move selected items from active to opposite list (F6)', self._command_move),
				('Create', 'Create new directory (F7)\nCreate new file (CTRL+F7)', self._command_create),
				('Delete', 'Delete selected items (F8 or Delete)', self._command_delete)
			)
		style = self.command_bar.get_style().copy()

		# create buttons and pack them
		for text, tooltip, callback in buttons:
			button = gtk.Button(label=text)

			if callback is not None:
				button.connect('clicked', callback)

			button.set_tooltip_text(tooltip)
			button.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_NORMAL])
			button.modify_fg(gtk.STATE_NORMAL, style.fg[gtk.STATE_NORMAL])
			button.set_focus_on_click(False)

			button.show()

			self.command_bar.pack_start(button, True, True, 0)

		self.command_bar.set_property(
						'no-show-all',
						not self.options.getboolean('main', 'show_command_bar')
					)

		# pack gui
		vbox = gtk.VBox(False, 0)
		vbox.pack_start(menu_bar, expand=False, fill=False, padding=0)
		vbox.pack_start(self.toolbar, expand=False, fill=False, padding=0)

		vbox2 = gtk.VBox(False, 3)
		vbox2.set_border_width(3)
		vbox2.pack_start(hbox, expand=True, fill=True, padding=0)
		vbox2.pack_start(hbox2, expand=False, fill=False, padding=0)
		vbox2.pack_start(self.command_bar, expand=False, fill=False, padding=0)

		vbox.pack_start(vbox2, True, True, 0)
		self.add(vbox)

		# create bookmarks menu
		self._create_bookmarks_menu()

		# restore window size and position
		self._restore_window_position()

		# show widgets
		self.show_all()

	def _destroy(self, widget, data=None):
		"""Application desctructor"""
		self.save_tabs(self.left_notebook, 'left_notebook')
		self.save_tabs(self.right_notebook, 'right_notebook')

		self._save_window_position()

		self.save_config()

		gtk.main_quit()
		
	def _delete_event(self, widget, data=None):
		"""Handle delete event"""
		self.hide()
		self.indicator.adjust_visibility_items(False)
		
		return True  # prevent default handler
	
	def _create_bookmarks_menu(self):
		"""Create bookmarks menu as defined in options"""
		if self.menu_bookmarks is None:
			# menu does not exist, create it
			self.menu_bookmarks = gtk.Menu()
			
		else:
			# menu already exists, just remove items
			for item in self.menu_bookmarks.get_children():
				self.menu_bookmarks.remove(item)
		
		items = self.bookmark_options.options('bookmarks')
		items.sort()
		
		for item in items:
			data = self.bookmark_options.get('bookmarks', item).split(';', 1)
			item_data = {
					'label': data[0],
					'callback': self._handle_bookmarks_click,
					}
			menu_item = self.menu_manager.create_menu_item(item_data)
			menu_item.set_data('path', os.path.expanduser(data[1]))
			
			self.menu_bookmarks.append(menu_item)

		# add separator
		menu_item = self.menu_manager.create_menu_item({'type': 'separator'})
		self.menu_bookmarks.append(menu_item)
		
		# create additional options
		menu_item = self.menu_manager.create_menu_item({
										'label': 'Options',
										'submenu': (
												{
													'label': '_Add bookmark',
													'callback': self._add_bookmark,
												},
												{
													'label': '_Edit bookmarks',
													'callback': self.options_window._show,
													'data': 3
												},
											) 
									})
		self.menu_bookmarks.append(menu_item)
			
		# create mounts if specified
		if self.options.getboolean('main', 'show_mounts'):
			self._create_mounts_menu()
			
	def _get_bookmarks_menu_position(self, menu, button):
		"""Get bookmarks position"""
		window_x, window_y = self.window.get_position()
		button_x, button_y = button.translate_coordinates(self, 0, 0)
		button_h = button.get_allocation().height
		
		pos_x = window_x + button_x
		pos_y = window_y + button_y + button_h
		
		return (pos_x, pos_y, True)
	
	def _add_bookmark(self, widget, data=None):
		"""Show dialog for adding a new bookmark"""
		item_list = self.menu_bookmarks.get_data('list')		
		path = item_list.path
		dialog = AddBookmarkDialog(self, path)
		
		response = dialog.get_response()
		
		if response[0] == gtk.RESPONSE_OK:
			bookmarks = self.bookmark_options.options('bookmarks')
			
			name = 'b_{0}'.format(len(bookmarks) + 1)
			value = '{0};{1}'.format(response[1], response[2])
			
			self.bookmark_options.set('bookmarks', name, value)
			self._create_bookmarks_menu()
	
	def _handle_bookmarks_click(self, widget, data=None):
		"""Handle clicks on bookmark menu"""
		item_list = self.menu_bookmarks.get_data('list')
		
		if item_list is not None and hasattr(item_list, 'change_path'):
			path = widget.get_data('path')
			
			if os.path.isdir(path):
				# path is valid
				item_list.change_path(path)
				
			else:
				# invalid path, notify user
				dialog = gtk.MessageDialog(
										self,
										gtk.DIALOG_DESTROY_WITH_PARENT,
										gtk.MESSAGE_ERROR,
										gtk.BUTTONS_OK,
										"Bookmarked path does not exist or is not "
										"valid. If path is not local check if specified "
										"volume is mounted."
										"\n\n{0}".format(path)
										)
				dialog.run()
				dialog.destroy()
						
	def _create_mounts_menu(self):
		"""Create mounts menu"""
		pass
	
	def _tab_moved(self, notebook, child, page_num):
		"""Handle adding/moving tab accross notebooks"""
		if hasattr(child, 'update_notebook'):
			child.update_notebook(notebook)

	def _transfer_focus(self, notebook, data=None):
		"""Transfer focus from notebook to child widget in active tab"""
		selected_page = notebook.get_nth_page(notebook.get_current_page())
		selected_page._main_object.grab_focus()

	def _toggle_show_hidden_files(self, widget, data=None):
		"""Transfer option event to all the lists"""
		show_hidden = widget.get_active()
		self.options.set('main', 'show_hidden', ('False', 'True')[show_hidden])

		# update left notebook
		for index in range(0, self.left_notebook.get_n_pages()):
			page = self.left_notebook.get_nth_page(index)

			if hasattr(page, 'refresh_file_list'):
				page.refresh_file_list(widget, data)

		# update right notebook
		for index in range(0, self.right_notebook.get_n_pages()):
			page = self.right_notebook.get_nth_page(index)

			if hasattr(page, 'refresh_file_list'):
				page.refresh_file_list(widget, data)

	def _toggle_show_command_bar(self, widget, data=None):
		"""Show/hide command bar"""
		show_command_bar = widget.get_active()
		
		self.options.set('main', 'show_command_bar', ('False', 'True')[show_command_bar])
		self.command_bar.set_visible(show_command_bar)
			
	def _toggle_show_toolbar(self, widget, data=None):
		"""Show/hide toolbar"""
		show_toolbar = widget.get_active()

		self.options.set('main', 'show_toolbar', ('False', 'True')[show_toolbar])
		self.toolbar.set_visible(show_toolbar)

	def _get_active_object(self):
		"""Return active notebook object"""
		return self._active_object

	def _set_active_object(self, object):
		"""Set active object"""
		if object is not None:
			self._active_object = object

	def _load_history(self):
		"""Load history file and populate the command list"""
		self.command_list.clear()

		try:
			# try to load our history file
			for line in file(os.path.join(user.home, self.options.get('main', 'history_file'))):
				self.command_list.append((line.strip(),))
		except:
			pass

	def _command_reload(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, 'refresh_file_list'):
			active_object.refresh_file_list()

	def _command_edit(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, '_edit_selected'):
			active_object._edit_selected()

	def _command_copy(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, '_copy_files'):
			active_object._copy_files()

	def _command_move(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, '_move_files'):
			active_object._move_files()

	def _command_create(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, '_create_directory'):
			active_object._create_directory()

	def _command_delete(self, widget, data=None):
		"""Handle command button click"""
		active_object = self._get_active_object()

		if hasattr(active_object, '_delete_files'):
			active_object._delete_files()

	def _command_edit_key_press(self, widget, event):
		"""Handle key press in command edit"""

		result = False

		# generate state sting based on modifier state (control, alt, shift)
		state = "%d%d%d" % (
					bool(event.state & gtk.gdk.CONTROL_MASK),
					bool(event.state & gtk.gdk.MOD1_MASK),
					bool(event.state & gtk.gdk.SHIFT_MASK)
				)

		# retrieve human readable key representation
		key_name = gtk.gdk.keyval_name(event.keyval)

		if (key_name == 'Up' or key_name == 'Escape') and state == '000':
			self._get_active_object()._main_object.grab_focus()
			result = True

		return result

	def _save_window_position(self):
		"""Save window position to config"""
		self.unfullscreen()
		self.unmaximize()
		size = self.get_size()
		position = self.get_position()
		geometry = '{0}x{1}+{2}+{3}'.format(size[0], size[1], position[0], position[1])

		self.options.set('main', 'window', geometry)

	def _restore_window_position(self):
		"""Restore window position from config string"""
		self.parse_geometry(self.options.get('main', 'window'))

	def show_bookmarks_menu(self, widget=None, notebook=None):
		"""Position bookmarks menu properly and show it"""
		button = None
		
		if notebook is not None:
			# show request was triggered by global shortcut
			page = notebook.get_nth_page(notebook.get_current_page())
			if hasattr(page, '_bookmarks_button'):
				button = page._bookmarks_button
				
			self.menu_bookmarks.set_data('list', page)
			
		else:
			# button called for menu
			button = widget
		
		if button is not None:	
			self.menu_bookmarks.popup(
									None, None, 
									self._get_bookmarks_menu_position, 
									1, 0, button
									)

	def select_all(self, widget, data=None):
		"""Select all items in active list"""
		list = self._get_active_object()

		# ensure we don't make exception on terminal tabs
		if hasattr(list, 'select_all'):
			list.select_all()

	def unselect_all(self, widget, data=None):
		"""Unselect all items in active list"""
		list = self._get_active_object()

		# ensure we don't make exception on terminal tabs
		if hasattr(list, 'unselect_all'):
			list.unselect_all()

	def invert_selection(self, widget, data=None):
		"""Invert selection in active list"""
		list = self._get_active_object()

		if hasattr(list, 'invert_selection'):
			list.invert_selection()

	def select_with_pattern(self, widget, data=None):
		"""Ask user for selection pattern and
		select matching items"""

		list = self._get_active_object()

		if hasattr(list, 'select_all'):
			# create dialog
			dialog = InputDialog(self)

			dialog.set_title('Select items')
			dialog.set_label('Selection pattern (eg.: *.jpg):')
			dialog.set_text('*')

			# get response
			response = dialog.get_response()

			# release dialog
			dialog.destroy()

			# commit selection
			if response[0] == gtk.RESPONSE_OK:
				list.select_all(response[1])

	def unselect_with_pattern(self, widget, data=None):
		"""Ask user for selection pattern and
		select matching items"""

		list = self._get_active_object()

		if hasattr(list, 'unselect_all'):
			# create dialog
			dialog = InputDialog(self)

			dialog.set_title('Unselect items')
			dialog.set_label('Selection pattern (eg.: *.jpg):')
			dialog.set_text('*')

			# get response
			response = dialog.get_response()

			# release dialog
			dialog.destroy()

			# commit selection
			if response[0] == gtk.RESPONSE_OK:
				list.unselect_all(response[1])

	def run(self):
		"""Main application loop"""

		# load tabs in the left notebook
		if not self.load_tabs(self.left_notebook, 'left_notebook'):
			self.create_tab(self.left_notebook, FileList)

		# load tabs in the right notebook
		if not self.load_tabs(self.right_notebook, 'right_notebook'):
			self.create_tab(self.right_notebook, FileList)

		gtk.main()
		
	def create_tab(self, notebook, plugin_class=None, data=None):
		"""Safe create tab"""
		if data is None:
			new_tab = plugin_class(self, notebook)
		else:
			new_tab = plugin_class(self, notebook, data)

		index = notebook.append_page(new_tab, new_tab._tab_label)
		notebook.set_tab_reorderable(new_tab, True)
		notebook.set_tab_detachable(new_tab, True)

		if self.options.getboolean('main', 'focus_new_tab'):
			notebook.set_current_page(index)
			new_tab._main_object.grab_focus()

	def create_terminal_tab(self, notebook, path=None):
		"""Create terminal tab on selected notebook"""
		self.create_tab(notebook, SystemTerminal, path)

	def close_tab(self, notebook, child):
		"""Safely remove tab and it's children"""

		if notebook.get_n_pages() > 1:
			notebook.remove_page(notebook.page_num(child))

			del child
			
	def next_tab(self, notebook):
		"""Select next tab on given notebook"""

		first_page = 0
		last_page = notebook.get_n_pages() - 1

		if notebook.get_current_page() == last_page:
			self.set_active_tab(notebook, first_page)
		else:
			notebook.next_page()

		page = notebook.get_nth_page(notebook.get_current_page())
		page._main_object.grab_focus()

	def previous_tab(self, notebook):
		"""Select previous tab on given notebook"""

		first_page = 0
		last_page = notebook.get_n_pages() - 1

		if notebook.get_current_page() == first_page:
			self.set_active_tab(notebook, last_page)
		else:
			notebook.prev_page()

		page = notebook.get_nth_page(notebook.get_current_page())
		page._main_object.grab_focus()

	def set_active_tab(self, notebook, tab):
		"""Set active tab number"""
		notebook.set_current_page(tab)

	def goto_web(self, widget, data=None):
		"""Open URL stored in data"""

		if data is not None:
			webbrowser.open_new_tab("http://%s" % data)

	def execute_command(self, widget, data=None):
		"""Executes system command"""
		if data is not None:
			# process custom data
			raw_command = data
		else:
			# no data is specified so we try to process command entry
			raw_command = self.command_edit.get_text()
			self.command_edit.insert_text(raw_command)
			self.command_edit.set_text('')

		handled = False
		active_object = self._get_active_object()
		command = raw_command.split(' ', 1)

		# return if we don't have anything to parse
		if len(command) < 2: return

		if command[0] == 'cd' and hasattr(active_object, 'change_path'):
			# handle CD command
			if os.path.isdir(os.path.join(active_object.path, command[1])):
				active_object.change_path(os.path.join(active_object.path, command[1]))
				active_object._main_object.grab_focus()

			handled = True

		if not handled:
			print "Unhandled command: {0}".format(command[0])

	def save_tabs(self, notebook, section):
		"""Save opened tabs"""

		self.tab_options.remove_section(section)
		self.tab_options.add_section(section)

		for index in range(0, notebook.get_n_pages()):
			page = notebook.get_nth_page(index)

			tab_class = page.__class__.__name__
			tab_path = page.path

			self.tab_options.set(
							section,
							'tab_{0}'.format(index),
							'{0}:{1}'.format(tab_class, tab_path)
						)

		if not self.tab_options.has_section('options'):
			self.tab_options.add_section('options')
			
		self.tab_options.set(
					'options', 
					'{0}_selected'.format(section), 
					notebook.get_current_page()
				)

	def load_tabs(self, notebook, section):
		"""Load saved tabs"""
		result = False

		if self.tab_options.has_section(section):
			# if section exists, load it
			tab_list = self.tab_options.options(section)
			tab_list.sort()
			
			for tab in tab_list:
				data = self.tab_options.get(section, tab).split(':', 1)

				tab_class = data[0]
				tab_path = data[1]

				self.create_tab(notebook, globals()[tab_class], tab_path)

			result = True

			# set active tab
			active_tab = self.tab_options.getint(
										'options', 
										'{0}_selected'.format(section)
									)
			self.set_active_tab(notebook, active_tab)

		return result

	def save_accel_map(self, path):
		"""Save menu accelerator map"""
		gtk.accel_map_save(path)
	
	def load_accel_map(self, path):
		"""Load menu accelerator map"""
		if os.path.isfile(path):
			gtk.accel_map_load(path)
		
		else:
			# no existing configuration, set default
			accel_map = (
						('<Sunflower>/Mark/SelectAll', 'A', gtk.gdk.CONTROL_MASK),
						('<Sunflower>/Mark/SelectPattern', 'KP_Add', 0),
						('<Sunflower>/Mark/UnselectPattern', 'KP_Subtract', 0),
						('<Sunflower>/Mark/InvertSelection', 'KP_Multiply', 0),
						('<Sunflower>/Mark/Compare', 'F12', 0),
						('<Sunflower>/Settings/ShowHidden', 'H', gtk.gdk.CONTROL_MASK),
						('<Sunflower>/Settings/Options', 'P', gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK),
						)
			
			for path, key, mask in accel_map:
				gtk.accel_map_change_entry(path, gtk.gdk.keyval_from_name(key), mask, True)
	
	def save_config(self):
		"""Save configuration to file"""
		try:
			if not os.path.isdir(self.config_path):
				os.makedirs(self.config_path)
				
			self.options.write(open(os.path.join(self.config_path, 'config'), 'w'))
			self.tab_options.write(open(os.path.join(self.config_path, 'tabs'), 'w'))
			self.bookmark_options.write(open(os.path.join(self.config_path, 'bookmarks'), 'w'))
			self.toolbar_options.write(open(os.path.join(self.config_path, 'toolbar'), 'w'))
			self.save_accel_map(os.path.join(self.config_path, 'accel_map'))

		except IOError as error:
			# notify user about failure
			dialog = gtk.MessageDialog(
									self,
									gtk.DIALOG_DESTROY_WITH_PARENT,
									gtk.MESSAGE_ERROR,
									gtk.BUTTONS_OK,
									"Error saving configuration to files"
									"in your home directory. "
									"Make sure you have enough permissions."
									"\n\n{0}".format(error)
									)
			dialog.run()
			dialog.destroy()

	def load_config(self):
		"""Load configuration from file located in users home directory"""

		self.options = RawConfigParser()
		self.tab_options = RawConfigParser()
		self.bookmark_options = RawConfigParser()
		self.toolbar_options = RawConfigParser()
		
		# load configuration from right folder on systems that support it 
		if os.path.isdir(os.path.join(user.home, '.config')):
			self.config_path = os.path.join(user.home, '.config', 'sunflower')
		else:
			self.config_path = os.path.join(user.home, '.sunflower')
	
		self.options.read(os.path.join(self.config_path, 'config'))
		self.tab_options.read(os.path.join(self.config_path, 'tabs'))
		self.bookmark_options.read(os.path.join(self.config_path, 'bookmarks'))
		self.toolbar_options.read(os.path.join(self.config_path, 'toolbar'))

		# set default values
		if not self.options.has_section('main'):
			self.options.add_section('main')
			
		if not self.bookmark_options.has_section('bookmarks'):
			self.bookmark_options.add_section('bookmarks')

		# define default options
		default_options = {
				'default_editor': 'gedit "{0}"',
				'wait_for_editor': 'False',
				'status_text': 'Directories: %dir_sel/%dir_count   '
							'Files: %file_sel/%file_count   '
							'Size: %size_sel/%size_total',
				'show_hidden': 'False',
				'show_mounts': 'True',
				'show_toolbar': 'False',
				'show_command_bar': 'False',
				'search_modifier': '010',
				'time_format': '%H:%M %d-%m-%y',
				'focus_new_tab': 'True',
				'row_hinting': 'False',
				'grid_lines': 0,
				'selection_color': 'red',
				'history_file': '.bash_history',
				'window': '950x450',
				'hide_on_close': 'True',
			}

		# set default options
		for option, value in default_options.items():
			if not self.options.has_option('main', option):
				self.options.set('main', option, value)

		# save default column sizes for file list
		if not self.options.has_section('FileList'):
			self.options.add_section('FileList')
			for i, size in enumerate([200, 50, 70, 50, 100]):
				self.options.set('FileList', 'size_{0}'.format(i), size)

	def focus_oposite_list(self, widget, data=None):
		"""Sets focus on oposite item list"""

		# get current tab container
		container = self.left_notebook.get_nth_page(
											self.left_notebook.get_current_page()
										)

		if container._main_object.get_property('has-focus'):
			self.right_notebook.grab_focus()
		else:
			self.left_notebook.grab_focus()

		return True

	def update_column_sizes(self, column, sender=None):
		"""Update column size on all tabs of specified class"""

		# update left notebook
		for index in range(0, self.left_notebook.get_n_pages()):
			page = self.left_notebook.get_nth_page(index)

			if isinstance(page, sender.__class__) and page is not sender:
				page.update_column_size(column.size_id)

		# update right notebook
		for index in range(0, self.right_notebook.get_n_pages()):
			page = self.right_notebook.get_nth_page(index)

			if isinstance(page, sender.__class__) and page is not sender:
				page.update_column_size(column.size_id)

	def toggle_fullscreen(self, widget, data=None):
		"""Toggle application fullscreen"""

		if self._in_fullscreen:
			self.unfullscreen()
			self._in_fullscreen = False

		else:
			self.fullscreen()
			self._in_fullscreen = True
			
	def add_operation(self, widget, callback, data=None):
		"""Add operation to menu"""
		item = gtk.MenuItem()
		item.add(widget)
		item.connect('activate', callback, data)
		
		item.show_all()
		item.hide()
		
		self.menu_operations.append(item)
		
		return item
	
	def remove_operation(self, widget):
		"""Remove operation item from menu"""
		if widget.get_visible():
			self.operation_hidden()
			
		self.menu_operations.remove(widget)
	
	def operation_displayed(self):
		"""Increase count of visible operation menu items"""
		self._operations_visible += 1
		self._menu_item_operations.set_sensitive(True)
		
	def operation_hidden(self):
		"""Decrease cound of visible operation menu items"""
		self._operations_visible -= 1
		
		if self._operations_visible == 0:
			self._menu_item_operations.set_sensitive(False)

	def test(self, widget, data=None):
		vbox = gtk.VBox(False, 0)
		
		label = gtk.Label('Copying: /var/files/home/njak')
		label.set_alignment(0, 0.5)
		progress = gtk.ProgressBar()
		
		vbox.pack_start(label, False, False, 0)
		vbox.pack_start(progress, False, False, 0)
		
		self.add_operation(vbox, None, None)
		
		