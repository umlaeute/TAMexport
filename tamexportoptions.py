#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2020  IOhannes m zmölnig
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
export a family-tree as JSON, usable with topographic attribute map (https://github.com/rpreiner/tam/)"""

#  GUI:
#    - disable "nobody is selected" dialog when no edge-people are selected
#    - fix descriptions

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from __future__ import unicode_literals
from functools import partial

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
log = logging.getLogger(".TAMexport.Options")

#------------------------------------------------------------------------
#
# GRAMPS module
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import stdoptions
from gramps.gen.plug.menu import Option
from gramps.gen.plug.menu import (NumberOption, ColorOption, BooleanOption,
                                  EnumeratedListOption, PersonListOption,
                                  SurnameColorOption)
from gramps.gen.utils.thumbnails import (SIZE_NORMAL, SIZE_LARGE)

#------------------------------------------------------------------------
#
# A quick overview of the classes we'll be using:
#
#   class TAMexportOptions(MenuReportOptions)
#       - this class is created when the report dialog comes up
#       - all configuration controls for the report are created here
#       - see src/ReportBase/_ReportOptions.py for more information
#
# Likely to be of additional interest is register_report() at the
# very bottom of this file.
#
#------------------------------------------------------------------------

class TAMexportOptions(MenuReportOptions):
    """
    Defines all of the controls necessary
    to configure the FamilyLines report.
    """
    def __init__(self, name, dbase):
        self.limit_parents = None
        self.max_parents = None
        self.limit_children = None
        self.max_children = None
        self.include_images = None
        self.image_location = None
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):

        # ---------------------
        category_name = _('Report Options')
        add_option = partial(menu.add_option, category_name)
        # ---------------------

        #stdoptions.add_name_format_option(menu, category_name)
        #stdoptions.add_private_data_option(menu, category_name, default=False)

        add_option('followpar', Option(_('Follow parents to determine '
                                    '"family lines"'), True))
        add_option('followchild', Option(_('Follow children to determine '
                                    '"family lines"'), True))

# what does *this* do???
        remove_extra_people = BooleanOption(_('Try to remove extra '
                                              'people and families'), True)
        remove_extra_people.set_help(_('People and families not directly '
                                       'related to people of interest will '
                                       'be removed when determining '
                                       '"family lines".'))
        add_option('removeextra', remove_extra_people)

        arrow = EnumeratedListOption(_("Arrowhead direction"), 'd')
        for i in range( 0, len(_ARROWS) ):
            arrow.add_item(_ARROWS[i]["value"], _ARROWS[i]["name"])
        arrow.set_help(_("Choose the direction that the arrows point."))
        add_option("arrow", arrow)


        use_roundedcorners = BooleanOption(_('Use rounded corners'), False)
        use_roundedcorners.set_help(_('Use rounded corners to differentiate '
                                      'between women and men.'))
        add_option("useroundedcorners", use_roundedcorners)

        stdoptions.add_gramps_id_option(menu, category_name, ownline=True)

        # ---------------------
        category_name = _('Report Options (2)')
        add_option = partial(menu.add_option, category_name)
        # ---------------------

        stdoptions.add_name_format_option(menu, category_name)
        stdoptions.add_private_data_option(menu, category_name, default=False)
        stdoptions.add_living_people_option(menu, category_name)
        locale_opt = stdoptions.add_localization_option(menu, category_name)
        stdoptions.add_date_format_option(menu, category_name, locale_opt)


        # --------------------------------
        add_option = partial(menu.add_option, _('Edge people'))
        # --------------------------------

        person_list = PersonListOption(_('Edge people'))
        person_list.set_help(_('Edge people are used as boundaries. '
                               'They will not be traversed when determining the full "family".'))
        add_option('edgelist', person_list)
        self.edgelist = person_list

        self.limit_parents = BooleanOption(_('Limit the number of ancestors'),
                                           False)
        self.limit_parents.set_help(_('Whether to '
                                      'limit the number of ancestors.'))
        add_option('limitparents', self.limit_parents)
        self.limit_parents.connect('value-changed', self.limit_changed)

        self.max_parents = NumberOption('', 50, 10, 9999)
        self.max_parents.set_help(_('The maximum number '
                                    'of ancestors to include.'))
        add_option('maxparents', self.max_parents)

        self.limit_children = BooleanOption(_('Limit the number '
                                              'of descendants'),
                                            False)
        self.limit_children.set_help(_('Whether to '
                                       'limit the number of descendants.'))
        add_option('limitchildren', self.limit_children)
        self.limit_children.connect('value-changed', self.limit_changed)

        self.max_children = NumberOption('', 50, 10, 9999)
        self.max_children.set_help(_('The maximum number '
                                     'of descendants to include.'))
        add_option('maxchildren', self.max_children)

        # --------------------------------
        add_option = partial(menu.add_option, _('Interesting people'))
        # --------------------------------
        add_option('gidlist', Option(_('Some people'), " "))

        # sometimes we don't want to list living people
        includeall_people = BooleanOption(_('Include all people'), False)
        includeall_people.set_help(_('Mark all people as interesting.'))
        add_option('allpeople', includeall_people)

        person_list = PersonListOption(_('Interesting people'))
        person_list.set_help(_('People whose families to include '
                               'apart from the "Main Person".'))
        add_option('interestlist', person_list)

        # sometimes we don't want to list living people
        anonymise_living_people = BooleanOption(_('Anonymize living people'), True)
        anonymise_living_people.set_help(_('Do not display names, dates and images of people '
                                       'that are still alive.'))
        add_option('livinganonymous', anonymise_living_people)

        # --------------------
        add_option = partial(menu.add_option, _('Include'))
        # --------------------

        include_id = EnumeratedListOption(_('Include Gramps ID'), 0)
        include_id.add_item(0, _('Do not include'))
        include_id.add_item(1, _('Share an existing line'))
        include_id.add_item(2, _('On a line of its own'))
        include_id.set_help(_("Whether (and where) to include Gramps IDs"))
        add_option("incid", include_id)

        self.include_dates = BooleanOption(_('Include dates'), True)
        self.include_dates.set_help(_('Whether to include dates for people '
                                      'and families.'))
        add_option('incdates', self.include_dates)
        self.include_dates.connect('value-changed', self.include_dates_changed)

        self.justyears = BooleanOption(_("Limit dates to years only"), False)
        self.justyears.set_help(_("Prints just dates' year, neither "
                                  "month or day nor date approximation "
                                  "or interval are shown."))
        add_option("justyears", self.justyears)

        include_places = BooleanOption(_('Include places'), True)
        include_places.set_help(_('Whether to include placenames for people '
                                  'and families.'))
        add_option('incplaces', include_places)

        include_num_children = BooleanOption(_('Include the number of '
                                               'children'), True)
        include_num_children.set_help(_('Whether to always include the number of '
                                        'children for families.'))
        add_option('incchildcnt', include_num_children)

        self.include_images = BooleanOption(_('Include '
                                              'thumbnail images of people'),
                                            True)
        self.include_images.set_help(_('Whether to '
                                       'include thumbnail images of people.'))
        add_option('incimages', self.include_images)
        self.include_images.connect('value-changed', self.images_changed)

        self.image_location = EnumeratedListOption(_('Thumbnail location'), 0)
        self.image_location.add_item(0, _('Above the name'))
        self.image_location.add_item(1, _('Beside the name'))
        self.image_location.set_help(_('Where the thumbnail image '
                                       'should appear relative to the name'))
        add_option('imageonside', self.image_location)

        self.image_size = EnumeratedListOption(_('Thumbnail size'), SIZE_NORMAL)
        self.image_size.add_item(SIZE_NORMAL, _('Normal'))
        self.image_size.add_item(SIZE_LARGE, _('Large'))
        self.image_size.set_help(_('Size of the thumbnail image'))
        add_option('imagesize', self.image_size)


        self.limit_changed()
        self.images_changed()

    def limit_changed(self):
        """
        Handle the change of limiting parents and children.
        """
        self.max_parents.set_available(self.limit_parents.get_value())
        self.max_children.set_available(self.limit_children.get_value())

    def images_changed(self):
        """
        Handle the change of including images.
        """
        self.image_location.set_available(self.include_images.get_value())

    def include_dates_changed(self):
        """
        Enable/disable menu items if dates are required
        """
        if self.include_dates.get_value():
            self.justyears.set_available(True)
        else:
            self.justyears.set_available(False)
