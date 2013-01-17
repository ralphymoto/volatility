# Volatility
# Copyright (C) 2007,2008 Volatile Systems
# Copyright (C) 2010,2011,2012 Michael Hale Ligh <michael.ligh@mnin.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. 
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 
#

import volatility.obj as obj
import volatility.utils as utils
import volatility.scan as scan
import volatility.plugins.common as common
import volatility.plugins.gui.windowstations as windowstations

class PoolScanAtom(scan.PoolScanner):
    """Pool scanner for atom tables"""

    def object_offset(self, found, address_space):
        """ This returns the offset of the object contained within
        this pool allocation.
        """
        pool_base = found - \
                self.buffer.profile.get_obj_offset('_POOL_HEADER', 'PoolTag')

        ## Note: all OS after XP, there are an extra 8 bytes (for 32-bit)
        ## or 16 bytes (for 64-bit) between the _POOL_HEADER and _RTL_ATOM_TABLE. 
        ## This is variable length structure, so we can't use the bottom-up
        ## approach as we do with other object scanners - because the size of an
        ## _RTL_ATOM_TABLE differs depending on the number of hash buckets. 

        build = (self.buffer.profile.metadata.get('major', 0),
                 self.buffer.profile.metadata.get('minor', 0))

        if self.buffer.profile.metadata.get('memory_model', '32bit') == '32bit':
            fixup = 8 if build > (5, 1) else 0
        else:
            fixup = 16 if build > (5, 1) else 0

        return pool_base + self.buffer.profile.get_obj_size('_POOL_HEADER') + fixup

    checks = [ ('PoolTagCheck', dict(tag = "AtmT")),
               ('CheckPoolSize', dict(condition = lambda x: x >= 200)),
               ('CheckPoolType', dict(paged = True, non_paged = True, free = True)),
               ]

class AtomScan(common.AbstractWindowsCommand):
    """Pool scanner for _RTL_ATOM_TABLE"""

    def __init__(self, config, *args, **kwargs):
        common.AbstractWindowsCommand.__init__(self, config, *args, **kwargs)

        config.add_option("SORT-BY", short_option = 'S', type = "choice",
                          choices = ["atom", "refcount", "offset"], default = "offset",
                          help = "Sort by [offset | atom | refcount]", action = "store")

    def calculate(self):
        flat_space = utils.load_as(self._config, astype = 'physical')
        kernel_space = utils.load_as(self._config)

        # Scan for atom tables
        for offset in PoolScanAtom().scan(flat_space):

            # There's no way to tell which session or window station 
            # owns an atom table by *just* looking at the atom table, 
            # so we have to instantiate it from the default kernel AS. 
            atom_table = obj.Object('_RTL_ATOM_TABLE', offset = offset,
                    vm = flat_space, native_vm = kernel_space)

            if atom_table.is_valid():
                yield atom_table

    def render_text(self, outfd, data):

        self.table_header(outfd,
                         [("TableOfs(P)", "[addr]"),
                          ("AtomOfs(V)", "[addrpad]"),
                          ("Atom", "[addr]"),
                          ("Refs", "6"),
                          ("Pinned", "6"),
                          ("Name", ""),
                         ])

        for atom_table in data:

            # This defeats the purpose of having a generator, but
            # its required if we want to be able to sort. We also
            # filter string atoms here. 
            atoms = [a for a in atom_table.atoms() if a.is_string_atom()]

            if self._config.SORT_BY == "atom":
                attr = "Atom"
            elif self._config.SORT_BY == "refcount":
                attr = "ReferenceCount"
            else:
                attr = "obj_offset"

            for atom in sorted(atoms, key = lambda x: getattr(x, attr)):

                self.table_row(outfd,
                    atom_table.obj_offset,
                    atom.obj_offset,
                    atom.Atom, atom.ReferenceCount,
                    atom.Pinned,
                    str(atom.Name or "")
                    )

class Atoms(common.AbstractWindowsCommand):
    """Print session and window station atom tables"""

    def calculate(self):
        seen = []

        # Find the atom tables that belong to each window station 
        for wndsta in windowstations.WndScan(self._config).calculate():

            offset = wndsta.obj_native_vm.vtop(wndsta.pGlobalAtomTable)
            if offset in seen:
                continue
            seen.append(offset)

            # The atom table is dereferenced in the proper 
            # session space 
            atom_table = wndsta.AtomTable

            if atom_table.is_valid():
                yield atom_table, wndsta

        # Find atom tables not linked to specific window stations. 
        # This finds win32k!UserAtomHandleTable. 
        for table in AtomScan(self._config).calculate():
            if table.PhysicalAddress not in seen:
                yield table, obj.NoneObject("No windowstation")

    def render_text(self, outfd, data):

        self.table_header(outfd,
                         [("Offset(P)", "[addr]"),
                          ("Session", "^10"),
                          ("WindowStation", "^18"),
                          ("Atom", "[addr]"),
                          ("RefCount", "^10"),
                          ("HIndex", "^10"),
                          ("Pinned", "^10"),
                          ("Name", ""),
                         ])

        for atom_table, window_station in data:
            for atom in atom_table.atoms():
            
                ## Filter string atoms 
                if not atom.is_string_atom():
                    continue 
            
                self.table_row(outfd,
                    atom_table.PhysicalAddress,
                    window_station.dwSessionId,
                    window_station.Name,
                    atom.Atom,
                    atom.ReferenceCount,
                    atom.HandleIndex,
                    atom.Pinned,
                    str(atom.Name or "")
                    )