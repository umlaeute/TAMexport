TAM exporter for gramps
=======================

This is a plugin for the [Genealogical Research Software - GRAMPS](https://gramps-project.org/)
to export a family tree (or parts thereof) in a format that can be used as a
[Topographic Attribute Map](https://github.com/rpreiner/tam/), for a nice visualisation of your family tree.


# Installation
- download the [latest version](https://github.com/umlaeute/TAMexport/archive/master.zip)
- unzip the file
- rename the directory to `TAMexport` (the default `TAMexport-master` or similar is wrong)
- move the `TAMexport` directory into your gramps plugins-folder.
  - linux: `~/.gramps/gramps51/plugins/`
  - window: ?
  - macOS: ?
- restart gramps

# Usage

## exporting data from gramps
Once you have opened a family tree, navigate to
- <kbd>Report</kbd> -> <kbd>Code Generators</kbd> -> <kbd>TAM exporter...</kbd>
- in the dialog window, you can control a bit which parts of your family tree should be included in the export
  - if you want *all* people of your database included,
    make sure to **check** the *Include all people* checkbox in the <kbd>Interesting People</kbd> section.
  - if you only want to include people that are somehow related to one or more people, **uncheck** this checkbox,
    and instead add a few people to the <kbd>Interesting people</kbd> panel.
    The *active person* is always part of the *Interesting people* (even if not displayed)
- you can also exclude parts of family tree by
  - adding people to the <kbd>Edge people</kbd> panel.
    When exporting your database, the plugin will start with the *Interesting people* and include all of their
    parents, children, siblings and spouses. Then it will proceed to include the parents, children, siblings
    and spouses of the relatives of the "interesting people" and so on.
    Whenever an *Edge person* is encountered, this database traversal stops (so edge people are included, but
    their relatives not - unless these relatives are reachable via some other person)
- once you are happy, select a file to export the data to (it should have the `.json` extension) and click on <kbd>OK</kbd>.

## importing data to TAM

- download [TAM](https://github.com/rpreiner/tam/)
- copy the JSON-file you just created with the *TAMexporter* into TAM's `data/` directory.
- using a text-editor (like `notepad` on Windows) open up TAM's `index.htm`
  - at the very end of the file you will see something like

        var PARAM_FILENAME = "MA.json"

  - replace the `MA.json` with the name of your exported file (it should probably not contain any spaces)
  - save the `index.htm` file and close it
- double-click on the `index.htm` file to open it with your browser
- enjoy

# LICENSE

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, version 2.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program.  If not, see <http://www.gnu.org/licenses/>.
