#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  IOhannes m zmölnig
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

# FIXXME: register_date_handler() for a 'YYYY'-format



"""
export a family-tree as JSON, usable with topographic attribute map (https://github.com/rpreiner/tam/)
"""


# new persons-of-interest algorithm:
## - allow selection of edge-people (currently: persons-of-interest; we just abuse this set, probably with another label in the GUI)
## - if no edge-people are selected, add ALL people to the report
## - else:
##      1. start with home-person
##      2. if person is not an edge person, add all SPOUSES, CHILDREN, PARENTS and SIBLINGS


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
log = logging.getLogger(".TAMexport")

#------------------------------------------------------------------------
#
# GRAMPS module
#
#------------------------------------------------------------------------
from gramps.gen.errors import HandleError
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.lib import AttributeType, EventRoleType, EventType, Person, PlaceType, NameType, FamilyRelType
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.thumbnails import get_thumbnail_path
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import Report
from gramps.gen.utils.db import get_timeperiod
from gramps.gen.utils.location import get_main_location

#------------------------------------------------------------------------
#
# A quick overview of the classes we'll be using:
#
#   class TAMexportOptions(MenuReportOptions)
#       - this class is created when the report dialog comes up
#       - all configuration controls for the report are created here
#       - see src/ReportBase/_ReportOptions.py for more information
#
#   class TAMexportReport(Report)
#       - this class is created only after the user clicks on "OK"
#       - the actual report generation is done by this class
#       - see src/ReportBase/_Report.py for more information
#
# Likely to be of additional interest is register_report() at the
# very bottom of this file.
#
#------------------------------------------------------------------------

def _getDefaultName(person):
    # GIVEN "NICK" SURNAME SUFFIX (geb. BIRTH)
    import re
    names = []
    try:
        prim = person.get_primary_name()
        surname = prim.get_surname()
        given = prim.get_first_name()
        nick = prim.get_nick_name()
        call = prim.get_call_name()
        suffix = prim.get_suffix()
        if call:
            given = re.sub(r"\b%s\b" % (call,), "<b>%s</b>" % (call,), given, 1)
        elif given:
            given = "<b>%s</b>" % given
        if surname:
            surname = "<b>%s</b>" % surname

        birth = None
        if prim.get_type() != NameType.BIRTH:
            ## check whether the person has a birth-name
            for a in person.get_alternate_names():
                if a.get_type() == NameType.BIRTH:
                    birth=a.get_surname()
                    if birth:
                        break

        names.append(given)
        if nick:
            names.append('"%s"' % (nick,))
        names.append(surname)
        names.append(suffix)
        if birth:
            names.append("(geb. %s)" % (birth,))

    except Exception as e:
        log.warning("failed constructing name", exc_info=True)
        return ''

    return ' '.join([_ for _ in names if _])


def _getLocationName(location, types=None):
    if not types:
        types=[PlaceType.PARISH,
               PlaceType.MUNICIPALITY,
               PlaceType.VILLAGE,
               PlaceType.TOWN,
               PlaceType.CITY,
               PlaceType.STATE,
               PlaceType.COUNTRY]
    #print("finding %s in %s" % (types, location))
    for t in types:
        s=location.get(t)
        if s:
            return s
    return None

def filterEdgePeople(db, people=set(), edgepeople=set(), incprivate=False):
    class Filter:
        def __init__(self, db, interestingpeople, edgepeople, incprivate):
            ## recursively process, starting with _homeperson:
            ### if currentperson in _people: break
            ### add currentperson to _people
            ### if currentperson is in edgepeople: break
            ### else:
            ###   add all families of currentperson to _families
            ###   recurse with all parents
            ###   recurse with all children
            ###   recurse with all spouses
            self._people=set()
            self._families=set()

            self._db=db
            self._incprivate=incprivate
            self._interesting=set(interestingpeople)
            self._edgepeople=edgepeople.difference(self._interesting)

            for person in self._interesting:
                self._recurse(person)

        def _recurse(self, handle):
            if not handle:
                return
            if handle in self._people:
                return

            person = self._db.get_person_from_handle(handle)
            # if this is a private record, and we're not
            # including private records, then go back to the
            # top of the while loop to get the next person

            if person.private and not self._incprivate:
                return

            # remember this person!
            self._people.add(handle)

            # if this person is an edge-case, we are done
            if handle in self._edgepeople:
                return

            ## find spouses and children
            ## by walking through all families were we are parent
            for family_handle in person.get_family_handle_list():
                if not family_handle in self._families:
                    self._families.add(family_handle)
                    family = self._db.get_family_from_handle(family_handle)

                    ## add spouse
                    spouse_handle = ReportUtils.find_spouse(person, family)
                    self._recurse(spouse_handle)

                    ## add children
                    for child_ref in family.get_child_ref_list():
                        self._recurse(child_ref.ref)

            ## find parents
            for family_handle in person.get_parent_family_handle_list():
                if not family_handle in self._families:
                    self._families.add(family_handle)
                    family = self._db.get_family_from_handle(family_handle)

                    ## add parents
                    self._recurse(family.get_father_handle())
                    self._recurse(family.get_mother_handle())
                    ## add siblings
                    for sibling_ref in family.get_child_ref_list():
                        self._recurse(sibling_ref.ref)


    f=Filter(db, people, edgepeople, incprivate)
    import sys
    sys.stdout.flush()
    return (f._people, f._families)

#------------------------------------------------------------------------
#
# TAMexportReport -- created once the user presses 'OK'
#
#------------------------------------------------------------------------
class TAMexportReport(Report):
    def __init__(self, database, options, user):
        """
        Create TAMexportReport object that eventually produces the report.

        The arguments are:

        database    - the GRAMPS database instance
        options     - instance of the TAMexportOptions class for this report
        user        - a gen.user.User() instance
        """
        Report.__init__(self, database, options, user)

        # initialize several convenient variables
        self._people = set() # handle of people we need in the report
        self._families = set() # handle of families we need in the report
        self._followparents = True
        self._followchild = True
        self._deleted_people = 0
        self._deleted_families = 0

        menu = options.menu
        get_value = lambda name: menu.get_option_by_name(name).get_value()

        self._removeextra = get_value('removeextra')
        interestlist = get_value('interestlist')
        edgelist = get_value('edgelist')
        self._limitparents = get_value('limitparents')
        self._maxparents = get_value('maxparents')
        self._limitchildren = get_value('limitchildren')
        self._maxchildren = get_value('maxchildren')

        # TODO: is there a standard-option for this?
        self._incdates = get_value('incdates')
        # TODO: use the standard-option 'living_people' for this
        self._livinganonymous = get_value('livinganonymous')

        self._incprivate = get_value('incl_private')

        include_all = get_value('allpeople')

        # this is only useful for name-formatting
        lang = menu.get_option_by_name('trans').get_value()
        self._locale = self.set_locale(lang)


        # the edgelist is annoying for us to use since we always have to convert
        # the GIDs to either Person or to handles, so we may as well convert the
        # entire list right now and not have to deal with it ever again
        self._edge_set = set()
        self._interest_set = set()
        # interesting people: the homeperson and the interestlist
        homeperson = self.database.get_default_person()
        if homeperson:
            self._interest_set.add(homeperson.get_handle())
        if interestlist:
            for gid in interestlist.split():
                person = self.database.get_person_from_gramps_id(gid)
                if person:
                    #option can be from another family tree, so person can be None
                    self._interest_set.add(person.get_handle())
        if not self._interest_set:
            print("empty interest set, everybody is interesting")
            include_all = True
        if include_all:
            for cnt, prs in enumerate(self.database.iter_people()):
                self._interest_set.add(prs.get_handle())

        # edge people: the edgelist
        if edgelist:
            for gid in edgelist.split():
                person = self.database.get_person_from_gramps_id(gid)
                if person:
                    #option can be from another family tree, so person can be None
                    self._edge_set.add(person.get_handle())
        else:
            print("empty edgelist")

        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)
            self.format_name = self._name_display.display
        else:
            self.format_name = _getDefaultName

    def begin_report(self):
        """
        Inherited method; called by report() in _ReportDialog.py

        This is where we'll do all of the work of figuring out who
        from the database is going to be output into the report
        """

        # starting with the people of interest, we then add parents:
        self._people.clear()
        self._families.clear()

        if self._edge_set:
            ## user provided a list of interesting (edge) people
            (p,f) = filterEdgePeople(
                self.database,
                self._interest_set, self._edge_set,
                self._incprivate)

            self._people.update(p)
            self._families.update(f)
            ### estimate dates
            self.estimate_person_times()
            return

        ## no list of interesting edge people provided by the user
        ## this means that we should use ALL people
        ## we re-use the original code but have set the _interest_set to ALL people
        ## in the ctor (ugly, but works)
        if self._followparents:
            self.findParents()

            if self._removeextra:
                self.removeUninterestingParents()

        # ...and/or with the people of interest we add their children:
        if self._followchild:
            self.findChildren()
        # once we get here we have a full list of people
        # and families that we need to generate a report

        ### estimate dates
        self.estimate_person_times()

    def write_report(self):
        """
        Inherited method; called by report() in _ReportDialog.py
        """
        import json

        filename = "/tmp/tam.json"
        print("***FIXME*** exporting to '%s' rather than the user-selected file" % (filename,))

        # now that begin_report() has done the work, output what we've
        # obtained into whatever file or format the user expects to use
        data = {
            "nodes": self.getPeople(),
            "links": self.getFamilies(),
        }
        with open(filename, "w") as f:
            json.dump(data, f)


    def _estimate_person_times(self, estimator=None):
        missing = 0
        if estimator is None:
            estimator = self.get_estimated_persontime
        for h in self._people:
            person = self.database.get_person_from_handle(h)
            id = person.get_gramps_id()
            if id in self._peopledates:
                continue
            date = estimator(person)
            if date:
                self._peopledates[id] = date
            else:
                missing += 1
        return missing


    def estimate_person_times(self):
        self._peopledates = {}
        # fill in known dates for a person
        missing = self._estimate_person_times()
        # estimate dates of a person based on their relations
        oldmiss = missing + 1
        print("estimating person times: missing=%s" % (missing,))
        while missing and oldmiss > missing:
            oldmiss = missing
            missing = self._estimate_person_times(self.person_time_of_peers)
            print("still missing: %s" % (missing,))

    def person_time_of_peers(self, person):
        x = self._person_time_of_peers(person)
        if x:
            print("estimated '%s' at %s" % (person.get_gramps_id(), x))
        return x
    def _person_time_of_peers(self, person):
        # assume that this person doesn't have any date attached directly to them

        # estimate of earliest age when one becomes a parent
        birther_age = 20

        def handlefun2age(handlefun):
            id = self.as_gramps_id(handlefun)
            if not id:
                return None
            return self._peopledates.get(id)

        def families2ages(family_handles, parent_births, children_births):
            for family_handle in family_handles:
                family = self.database.get_family_from_handle(family_handle)
                # to get the birth-date of the youngest parent (if any)
                parent_births.append(handlefun2age(family.get_father_handle))
                parent_births.append(handlefun2age(family.get_mother_handle))
                # and the birth-dates of all the siblings
                for sib in family.get_child_ref_list():
                    sibling = self.database.get_person_from_handle(sib.ref)
                    if sibling:
                        children_births.append(self._peopledates.get(sibling.get_gramps_id()))

        def mean(data):
            data = list(filter(None, data))
            if data:
                return sum(data) / len(data)

        def mapNotNone(fun, data):
            try:
                return fun(filter(None, data))
            except:
                pass

        parent_births = []
        child_births = []
        sibling_births = []
        spouse_births = []

        # iterate over all families, where 'person' is a child
        # to get the birth-date of the youngest parent (if any)
        # and the birth-dates of all the siblings
        families2ages(person.get_parent_family_handle_list(), parent_births, sibling_births)

        # iterate over all families, where 'person' is a spouse/parent
        # to get the birth-date of the oldest child (if any)
        # and the birth-dates of all the spouses
        families2ages(person.get_family_handle_list(), spouse_births, child_births)

        ## get the youngest parent
        parent_birth=mapNotNone(max, parent_births)
        ## get the oldest child
        child_birth=mapNotNone(min, child_births)
        ## get the mean age of spouses
        spouse_birth = mean(spouse_births)
        ## get the mean age of siblings
        sibling_birth = mean(sibling_births)

        ## if both parent and child have a date, our person must be born somewhen inbetween
        if child_birth and parent_birth:
            return int((child_birth + parent_birth)/2)
        ## otherwise, the person must be older than the child
        if child_birth:
            return child_birth - birther_age
        ## and of course younger than their parents
        if parent_birth:
            return parent_birth + birther_age

        ## if none of this worked, check if we have siblings
        ## and assume that we are "about the same age" (mean of all siblings with dates)
        if sibling_birth:
            return int(sibling_birth)

        ## if we still don't know anything, check if we have a spouse, and assume the same age
        if spouse_birth:
            return int(spouse_birth)

        return None

    def get_estimated_persontime(self, person):
        date = self._peopledates.get(person.get_gramps_id(), None)
        if date is not None:
            return date
        date = get_timeperiod(self.database, person)
        if date is not None:
            try:
                return date.get_date_object().get_year()
            except:
                return date
        return  None


    def findParents(self):
        # we need to start with all of our "people of interest"
        ancestorsNotYetProcessed = set(self._interest_set)

        # now we find all the immediate ancestors of our people of interest

        while ancestorsNotYetProcessed:
            handle = ancestorsNotYetProcessed.pop()

            # One of 2 things can happen here:
            #   1) we've already know about this person and he/she is already
            #      in our list
            #   2) this is someone new, and we need to remember him/her
            #
            # In the first case, there isn't anything else to do, so we simply
            # go back to the top and pop the next person off the list.
            #
            # In the second case, we need to add this person to our list, and
            # then go through all of the parents this person has to find more
            # people of interest.

            if handle not in self._people:
                person = self.database.get_person_from_handle(handle)

                # if this is a private record, and we're not
                # including private records, then go back to the
                # top of the while loop to get the next person
                if person.private and not self._incprivate:
                    continue

                # remember this person!
                self._people.add(handle)

                # see if a family exists between this person and someone else
                # we have on our list of people we're going to output -- if
                # there is a family, then remember it for when it comes time
                # to link spouses together
                for family_handle in person.get_family_handle_list():
                    family = self.database.get_family_from_handle(family_handle)
                    spouse_handle = ReportUtils.find_spouse(person, family)
                    if spouse_handle:
                        if (spouse_handle in self._people or
                           spouse_handle in ancestorsNotYetProcessed):
                            self._families.add(family_handle)


                # if we have a limit on the number of people, and we've
                # reached that limit, then don't attempt to find any
                # more ancestors
                if self._limitparents and (self._maxparents <
                        len(ancestorsNotYetProcessed) + len(self._people)):
                    # get back to the top of the while loop so we can finish
                    # processing the people queued up in the "not yet
                    # processed" list
                    continue

                # queue the parents of the person we're processing
                for family_handle in person.get_parent_family_handle_list():
                    family = self.database.get_family_from_handle(family_handle)

                    if not family.private or self._incprivate:
                        try:
                            father = self.database.get_person_from_handle(
                                family.get_father_handle())
                        except AttributeError: father = None
                        try:
                            mother = self.database.get_person_from_handle(
                                family.get_mother_handle())
                        except AttributeError: mother = None
                        if father:
                            if not father.private or self._incprivate:
                                ancestorsNotYetProcessed.add(
                                                 family.get_father_handle())
                                self._families.add(family_handle)
                        if mother:
                            if not mother.private or self._incprivate:
                                ancestorsNotYetProcessed.add(
                                                 family.get_mother_handle())
                                self._families.add(family_handle)

                        for sib in family.get_child_ref_list():
                            sibling = self.database.get_person_from_handle(sib.ref)
                            if sibling and (not sibling.private or self._incprivate):
                                ancestorsNotYetProcessed.add(sib.ref)
                                self._families.add(family_handle)

    def removeUninterestingParents(self):
        # start with all the people we've already identified
        unprocessed_parents = set(self._people)

        while len(unprocessed_parents) > 0:
            handle = unprocessed_parents.pop()
            person = self.database.get_person_from_handle(handle)

            # There are a few things we're going to need,
            # so look it all up right now; such as:
            # - who is the child?
            # - how many children?
            # - parents?
            # - spouse?
            # - is a person of interest?
            # - spouse of a person of interest?
            # - same surname as a person of interest?
            # - spouse has the same surname as a person of interest?

            child_handle = None
            child_count = 0
            spouse_handle = None
            spouse_count = 0
            father_handle = None
            mother_handle = None
            spouse_father_handle = None
            spouse_mother_handle = None
            spouse_surname = ""
            surname = person.get_primary_name().get_surname()
            surname = surname.encode('iso-8859-1','xmlcharrefreplace')

            # first we get the person's father and mother
            for family_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)
                handle = family.get_father_handle()
                if handle in self._people:
                    father_handle = handle
                handle = family.get_mother_handle()
                if handle in self._people:
                    mother_handle = handle

            # now see how many spouses this person has
            for family_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)
                handle = ReportUtils.find_spouse(person, family)
                if handle in self._people:
                    spouse_count += 1
                    spouse = self.database.get_person_from_handle(handle)
                    spouse_handle = handle
                    spouse_surname = spouse.get_primary_name().get_surname()
                    spouse_surname = spouse_surname.encode(
                                        'iso-8859-1', 'xmlcharrefreplace'
                                        )

                    # see if the spouse has parents
                    if not spouse_father_handle and not spouse_mother_handle:
                        for family_handle in \
                          spouse.get_parent_family_handle_list():
                            family = self.database.get_family_from_handle(
                                                              family_handle)
                            handle = family.get_father_handle()
                            if handle in self._people:
                                spouse_father_handle = handle
                            handle = family.get_mother_handle()
                            if handle in self._people:
                                spouse_mother_handle = handle

            # get the number of children that we think might be interesting
            for family_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)
                if family.private and not self._incprivate:
                    for child_ref in family.get_child_ref_list():
                        if child_ref.ref in self._people:
                            child_count += 1
                            child_handle = child_ref.ref

            # we now have everything we need -- start looking for reasons
            # why this is a person we need to keep in our list, and loop
            # back to the top as soon as a reason is discovered

            # if this person has many children of interest, then we
            # automatically keep this person
            if child_count > 1:
                continue

            # if this person has many spouses of interest, then we
            # automatically keep this person
            if spouse_count > 1:
                continue

            # if this person has parents, then we automatically keep
            # this person
            if father_handle is not None or mother_handle is not None:
                continue

            # if the spouse has parents, then we automatically keep
            # this person
            if spouse_father_handle is not None or spouse_mother_handle is not None:
                continue

            # if this is a person of interest, then we automatically keep
            if person.get_handle() in self._interest_set:
                continue

            # if the spouse is a person of interest, then we keep
            if spouse_handle in self._interest_set:
                continue

            # if the surname (or the spouse's surname) matches a person
            # of interest, then we automatically keep this person
            bKeepThisPerson = False
            for personOfInterestHandle in self._interest_set:
                personOfInterest = self.database.get_person_from_handle(personOfInterestHandle)
                surnameOfInterest = personOfInterest.get_primary_name().get_surname().encode('iso-8859-1','xmlcharrefreplace')
                if surnameOfInterest == surname or surnameOfInterest == spouse_surname:
                    bKeepThisPerson = True
                    break

            if bKeepThisPerson:
                continue

            # if we have a special colour to use for this person,
            # then we automatically keep this person
            if surname in self._surnamecolors:
                continue

            # if we have a special colour to use for the spouse,
            # then we automatically keep this person
            if spouse_surname in self._surnamecolors:
                continue

            # took us a while, but if we get here, then we can remove this person
            self._deleted_people += 1
            self._people.remove(person.get_handle())

            # we can also remove any families to which this person belonged
            for family_handle in person.get_family_handle_list():
                if family_handle in self._families:
                    self._deleted_families += 1
                    self._families.remove(family_handle)

            # if we have a spouse, then ensure we queue up the spouse
            if spouse_handle:
                if spouse_handle not in unprocessed_parents:
                    unprocessed_parents.add(spouse_handle)

            # if we have a child, then ensure we queue up the child
            if child_handle:
                if child_handle not in unprocessed_parents:
                    unprocessed_parents.add(child_handle)


    def findChildren(self):
        # we need to start with all of our "people of interest"
        childrenNotYetProcessed = set(self._interest_set)
        childrenToInclude = set()

        # now we find all the children of our people of interest

        while len(childrenNotYetProcessed) > 0:
            handle = childrenNotYetProcessed.pop()

            if handle not in childrenToInclude:

                person = self.database.get_person_from_handle(handle)

                # if this is a private record, and we're not
                # including private records, then go back to the
                # top of the while loop to get the next person
                if person.private and not self._incprivate:
                    continue

                # remember this person!
                childrenToInclude.add(handle)

                # if we have a limit on the number of people, and we've
                # reached that limit, then don't attempt to find any
                # more children
                if self._limitchildren and (
                    self._maxchildren < (
                        len(childrenNotYetProcessed) + len(childrenToInclude)
                        )
                    ):
                    # get back to the top of the while loop so we can finish
                    # processing the people queued up in the "not yet processed" list
                    continue

                # iterate through this person's families
                for family_handle in person.get_family_handle_list():
                    family = self.database.get_family_from_handle(family_handle)
                    if (family.private and self._incprivate) or not family.private:

                        # queue up any children from this person's family
                        for childRef in family.get_child_ref_list():
                            child = self.database.get_person_from_handle(childRef.ref)
                            if (child.private and self._incprivate) or not child.private:
                                childrenNotYetProcessed.add(child.get_handle())
                                self._families.add(family_handle)

                        # include the spouse from this person's family
                        spouse_handle = ReportUtils.find_spouse(person, family)
                        if spouse_handle:
                            spouse = self.database.get_person_from_handle(spouse_handle)
                            if (spouse.private and self._incprivate) or not spouse.private:
                                childrenToInclude.add(spouse_handle)
                                self._families.add(family_handle)

        # we now merge our temp set "childrenToInclude" into our master set
        self._people.update(childrenToInclude)

    def getPeople(self):
        # loop through all the people we need to output
        def handle2json(handle):
            person = self.database.get_person_from_handle(handle)
            name = self.format_name(person)
            return  {
                "id": person.get_gramps_id(),
                "name": name,
                "value": self.get_estimated_persontime(person) or 0,
            }
        return [handle2json(_) for _ in self._people ]

    def as_gramps_id(self, fun):
        x = fun()
        if not x: return
        x = self.database.get_person_from_handle(x)
        if x:
            try:
                y = x.get_gramps_id()
                return y
            except: pass
        return None

    def getFamilies(self):
        def family2json(family):
            #{"source": "@I0032@", "target": "@I0036@", "directed": true},
            father = self.as_gramps_id(family.get_father_handle)
            mother = self.as_gramps_id(family.get_mother_handle)
            # link the children to the family
            result = []
            if father and mother:
                result.append({"source": father, "target": mother, "directed": False})
            for childRef in family.get_child_ref_list():
                if childRef.ref in self._people:
                    child = self.database.get_person_from_handle(childRef.ref)
                    if child:
                        child = child.get_gramps_id()
                    if child and father:
                        result.append({"source": father, "target": child, "directed": True})
                    if child and mother:
                        result.append({"source": mother, "target": child, "directed": True})
            return result

        # now that we have the families written, go ahead and link the parents and children to the families
        result = []
        for family_handle in self._families:
            # get the parents for this family
            family = self.database.get_family_from_handle(family_handle)
            result += family2json(family)
        return result



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
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import stdoptions
from gramps.gen.plug.menu import Option
from gramps.gen.plug.menu import (NumberOption, ColorOption, BooleanOption,
                                  EnumeratedListOption, PersonListOption,
                                  SurnameColorOption)

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
        MenuReportOptions.__init__(self, name, dbase)

        from gramps.gen.const import GRAMPS_LOCALE as glocale

    def add_menu_options(self, menu):

        # ---------------------
        category_name = _('Report Options')
        add_option = partial(menu.add_option, category_name)
        # ---------------------

        add_option('followpar', Option(_('Follow parents to determine '
                                    '"family lines"'), True))
        add_option('followchild', Option(_('Follow children to determine '
                                    '"family lines"'), True))

        stdoptions.add_name_format_option(menu, category_name)
        stdoptions.add_place_format_option(menu, category_name)
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

        remove_extra_people = BooleanOption(_('Try to remove extra '
                                              'people and families'), True)
        remove_extra_people.set_help(_('People and families not directly '
                                       'related to people of interest will '
                                       'be removed when determining '
                                       '"family lines".'))
        add_option('removeextra', remove_extra_people)

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

        self.include_dates = BooleanOption(_('Include dates'), True)
        self.include_dates.set_help(_('Whether to include dates for people.'))
        add_option('incdates', self.include_dates)

        self.limit_changed()

    def limit_changed(self):
        """
        Handle the change of limiting parents and children.
        """
        self.max_parents.set_available(self.limit_parents.get_value())
        self.max_children.set_available(self.limit_children.get_value())
