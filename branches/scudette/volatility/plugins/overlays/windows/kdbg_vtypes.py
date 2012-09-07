# Volatility
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



class _KDDEBUGGER_DATA64(obj.CType):
    """A class for KDBG"""

    def is_valid(self):
        """Returns true if the kdbg_object appears valid"""
        # Check the OwnerTag is in fact the string KDBG
        return (super(_KDDEBUGGER_DATA64, self).is_valid() and
                self.Header.OwnerTag == 0x4742444B)

    @property
    def ServicePack(self):
        """Get the service pack number. This is something
        like 0x100 for SP1, 0x200 for SP2 etc.
        """
        csdresult = self.obj_profile.Object(
            "unsigned long", offset = self.CmNtCSDVersion, vm = self.obj_vm)
        return (csdresult >> 8) & 0xffffffff

    def dbgkd_version64(self):
        """Scan backwards from the base of KDBG to find the
        _DBGKD_GET_VERSION64. We have a winner when kernel
        base addresses and process list head match."""

        # Account for address masking differences in x86 and x64
        memory_model = self.obj_profile.metadata('memory_model', '32bit')

        dbgkd_off = self.obj_offset & 0xFFFFFFFFFFFFF000
        dbgkd_end = dbgkd_off + 0x1000
        dbgkd_size = self.obj_profile.get_obj_size("_DBGKD_GET_VERSION64")

        while dbgkd_off <= (dbgkd_end - dbgkd_size):

            dbgkd = self.obj_profile.Object(
                "_DBGKD_GET_VERSION64", offset = dbgkd_off, vm = self.obj_vm)

            if memory_model == "32bit":
                KernBase = dbgkd.KernBase & 0xFFFFFFFF
                PsLoadedModuleList = dbgkd.PsLoadedModuleList & 0xFFFFFFFF
            else:
                KernBase = dbgkd.KernBase
                PsLoadedModuleList = dbgkd.PsLoadedModuleList

            if ((KernBase == self.KernBase) and (PsLoadedModuleList == self.PsLoadedModuleList)):
                return dbgkd

            dbgkd_off += 1

        return obj.NoneObject("Cannot find _DBGKD_GET_VERSION64")

    def kpcrs(self):
        """Generator for KPCRs referenced by this KDBG.

        These are returned in the order in which the
        processors were registered.
        """

        if self.obj_profile.metadata('memory_model') == '32bit':
            prcb_member = "PrcbData"
        else:
            prcb_member = "Prcb"

        cpu_array = self.KiProcessorBlock.dereference()

        for p in cpu_array:

            # A null pointer indicates the end of the CPU list. Since
            # the 0 page is not valid in kernel AS, this single check
            # should match both NoneObject and null pointers.
            if not p:
                break

            kpcrb = p.dereference_as("_KPRCB")

            yield self.obj_profile.Object(
                "_KPCR",
                offset=(kpcrb.obj_offset -
                        self.obj_profile.get_obj_offset("_KPCR", prcb_member)),
                vm = self.obj_vm)


kdbg_overlay = {
    '_KDDEBUGGER_DATA64': [ None, {
            'NtBuildLab': [ None, ['pointer', ['String', dict(length = 32)]]],
            'KiProcessorBlock': [ None, [
                    'Pointer', {
                        'target': 'Array',
                        'target_args': {
                            'count': lambda x: 32 + 32 * int(
                                x.obj_profile.metadata("memory_model") == "64bit"),
                            "target": "Pointer",
                            "target_args": dict(target="_KPRCB"),
                            }
                        }]],
            }],
    }


kdbg_vtypes = {
'_DBGKD_DEBUG_DATA_HEADER64' : [  0x18, {
  'List' : [ 0x0, ['LIST_ENTRY64']],
  'OwnerTag' : [ 0x10, ['unsigned long']],
  'Size' : [ 0x14, ['unsigned long']],
} ],

'_KDDEBUGGER_DATA64' : [  0x340, {
  'Header' : [ 0x0, ['_DBGKD_DEBUG_DATA_HEADER64']],
  'KernBase' : [ 0x18, ['unsigned long long']],
  'BreakpointWithStatus' : [ 0x20, ['unsigned long long']],
  'SavedContext' : [ 0x28, ['unsigned long long']],
  'ThCallbackStack' : [ 0x30, ['unsigned short']],
  'NextCallback' : [ 0x32, ['unsigned short']],
  'FramePointer' : [ 0x34, ['unsigned short']],
  'KiCallUserMode' : [ 0x38, ['unsigned long long']],
  'KeUserCallbackDispatcher' : [ 0x40, ['unsigned long long']],
  'PsLoadedModuleList' : [ 0x48, ['unsigned long long']],
  'PsActiveProcessHead' : [ 0x50, ['unsigned long long']],
  'PspCidTable' : [ 0x58, ['unsigned long long']],
  'ExpSystemResourcesList' : [ 0x60, ['unsigned long long']],
  'ExpPagedPoolDescriptor' : [ 0x68, ['unsigned long long']],
  'ExpNumberOfPagedPools' : [ 0x70, ['unsigned long long']],
  'KeTimeIncrement' : [ 0x78, ['unsigned long long']],
  'KeBugCheckCallbackListHead' : [ 0x80, ['unsigned long long']],
  'KiBugcheckData' : [ 0x88, ['unsigned long long']],
  'IopErrorLogListHead' : [ 0x90, ['unsigned long long']],
  'ObpRootDirectoryObject' : [ 0x98, ['unsigned long long']],
  'ObpTypeObjectType' : [ 0xa0, ['unsigned long long']],
  'MmSystemCacheStart' : [ 0xa8, ['unsigned long long']],
  'MmSystemCacheEnd' : [ 0xb0, ['unsigned long long']],
  'MmSystemCacheWs' : [ 0xb8, ['unsigned long long']],
  'MmPfnDatabase' : [ 0xc0, ['unsigned long long']],
  'MmSystemPtesStart' : [ 0xc8, ['unsigned long long']],
  'MmSystemPtesEnd' : [ 0xd0, ['unsigned long long']],
  'MmSubsectionBase' : [ 0xd8, ['unsigned long long']],
  'MmNumberOfPagingFiles' : [ 0xe0, ['unsigned long long']],
  'MmLowestPhysicalPage' : [ 0xe8, ['unsigned long long']],
  'MmHighestPhysicalPage' : [ 0xf0, ['unsigned long long']],
  'MmNumberOfPhysicalPages' : [ 0xf8, ['unsigned long long']],
  'MmMaximumNonPagedPoolInBytes' : [ 0x100, ['unsigned long long']],
  'MmNonPagedSystemStart' : [ 0x108, ['unsigned long long']],
  'MmNonPagedPoolStart' : [ 0x110, ['unsigned long long']],
  'MmNonPagedPoolEnd' : [ 0x118, ['unsigned long long']],
  'MmPagedPoolStart' : [ 0x120, ['unsigned long long']],
  'MmPagedPoolEnd' : [ 0x128, ['unsigned long long']],
  'MmPagedPoolInformation' : [ 0x130, ['unsigned long long']],
  'MmPageSize' : [ 0x138, ['unsigned long long']],
  'MmSizeOfPagedPoolInBytes' : [ 0x140, ['unsigned long long']],
  'MmTotalCommitLimit' : [ 0x148, ['unsigned long long']],
  'MmTotalCommittedPages' : [ 0x150, ['unsigned long long']],
  'MmSharedCommit' : [ 0x158, ['unsigned long long']],
  'MmDriverCommit' : [ 0x160, ['unsigned long long']],
  'MmProcessCommit' : [ 0x168, ['unsigned long long']],
  'MmPagedPoolCommit' : [ 0x170, ['unsigned long long']],
  'MmExtendedCommit' : [ 0x178, ['unsigned long long']],
  'MmZeroedPageListHead' : [ 0x180, ['unsigned long long']],
  'MmFreePageListHead' : [ 0x188, ['unsigned long long']],
  'MmStandbyPageListHead' : [ 0x190, ['unsigned long long']],
  'MmModifiedPageListHead' : [ 0x198, ['unsigned long long']],
  'MmModifiedNoWritePageListHead' : [ 0x1a0, ['unsigned long long']],
  'MmAvailablePages' : [ 0x1a8, ['unsigned long long']],
  'MmResidentAvailablePages' : [ 0x1b0, ['unsigned long long']],
  'PoolTrackTable' : [ 0x1b8, ['unsigned long long']],
  'NonPagedPoolDescriptor' : [ 0x1c0, ['unsigned long long']],
  'MmHighestUserAddress' : [ 0x1c8, ['unsigned long long']],
  'MmSystemRangeStart' : [ 0x1d0, ['unsigned long long']],
  'MmUserProbeAddress' : [ 0x1d8, ['unsigned long long']],
  'KdPrintCircularBuffer' : [ 0x1e0, ['unsigned long long']],
  'KdPrintCircularBufferEnd' : [ 0x1e8, ['unsigned long long']],
  'KdPrintWritePointer' : [ 0x1f0, ['unsigned long long']],
  'KdPrintRolloverCount' : [ 0x1f8, ['unsigned long long']],
  'MmLoadedUserImageList' : [ 0x200, ['unsigned long long']],
  'NtBuildLab' : [ 0x208, ['unsigned long long']],
  'KiNormalSystemCall' : [ 0x210, ['unsigned long long']],
  'KiProcessorBlock' : [ 0x218, ['unsigned long long']],
  'MmUnloadedDrivers' : [ 0x220, ['unsigned long long']],
  'MmLastUnloadedDriver' : [ 0x228, ['unsigned long long']],
  'MmTriageActionTaken' : [ 0x230, ['unsigned long long']],
  'MmSpecialPoolTag' : [ 0x238, ['unsigned long long']],
  'KernelVerifier' : [ 0x240, ['unsigned long long']],
  'MmVerifierData' : [ 0x248, ['unsigned long long']],
  'MmAllocatedNonPagedPool' : [ 0x250, ['unsigned long long']],
  'MmPeakCommitment' : [ 0x258, ['unsigned long long']],
  'MmTotalCommitLimitMaximum' : [ 0x260, ['unsigned long long']],
  'CmNtCSDVersion' : [ 0x268, ['unsigned long long']],
  'MmPhysicalMemoryBlock' : [ 0x270, ['unsigned long long']],
  'MmSessionBase' : [ 0x278, ['unsigned long long']],
  'MmSessionSize' : [ 0x280, ['unsigned long long']],
  'MmSystemParentTablePage' : [ 0x288, ['unsigned long long']],
  'MmVirtualTranslationBase' : [ 0x290, ['unsigned long long']],
  'OffsetKThreadNextProcessor' : [ 0x298, ['unsigned short']],
  'OffsetKThreadTeb' : [ 0x29a, ['unsigned short']],
  'OffsetKThreadKernelStack' : [ 0x29c, ['unsigned short']],
  'OffsetKThreadInitialStack' : [ 0x29e, ['unsigned short']],
  'OffsetKThreadApcProcess' : [ 0x2a0, ['unsigned short']],
  'OffsetKThreadState' : [ 0x2a2, ['unsigned short']],
  'OffsetKThreadBStore' : [ 0x2a4, ['unsigned short']],
  'OffsetKThreadBStoreLimit' : [ 0x2a6, ['unsigned short']],
  'SizeEProcess' : [ 0x2a8, ['unsigned short']],
  'OffsetEprocessPeb' : [ 0x2aa, ['unsigned short']],
  'OffsetEprocessParentCID' : [ 0x2ac, ['unsigned short']],
  'OffsetEprocessDirectoryTableBase' : [ 0x2ae, ['unsigned short']],
  'SizePrcb' : [ 0x2b0, ['unsigned short']],
  'OffsetPrcbDpcRoutine' : [ 0x2b2, ['unsigned short']],
  'OffsetPrcbCurrentThread' : [ 0x2b4, ['unsigned short']],
  'OffsetPrcbMhz' : [ 0x2b6, ['unsigned short']],
  'OffsetPrcbCpuType' : [ 0x2b8, ['unsigned short']],
  'OffsetPrcbVendorString' : [ 0x2ba, ['unsigned short']],
  'OffsetPrcbProcStateContext' : [ 0x2bc, ['unsigned short']],
  'OffsetPrcbNumber' : [ 0x2be, ['unsigned short']],
  'SizeEThread' : [ 0x2c0, ['unsigned short']],
  'KdPrintCircularBufferPtr' : [ 0x2c8, ['unsigned long long']],
  'KdPrintBufferSize' : [ 0x2d0, ['unsigned long long']],
  'KeLoaderBlock' : [ 0x2d8, ['unsigned long long']],
  'SizePcr' : [ 0x2e0, ['unsigned short']],
  'OffsetPcrSelfPcr' : [ 0x2e2, ['unsigned short']],
  'OffsetPcrCurrentPrcb' : [ 0x2e4, ['unsigned short']],
  'OffsetPcrContainedPrcb' : [ 0x2e6, ['unsigned short']],
  'OffsetPcrInitialBStore' : [ 0x2e8, ['unsigned short']],
  'OffsetPcrBStoreLimit' : [ 0x2ea, ['unsigned short']],
  'OffsetPcrInitialStack' : [ 0x2ec, ['unsigned short']],
  'OffsetPcrStackLimit' : [ 0x2ee, ['unsigned short']],
  'OffsetPrcbPcrPage' : [ 0x2f0, ['unsigned short']],
  'OffsetPrcbProcStateSpecialReg' : [ 0x2f2, ['unsigned short']],
  'GdtR0Code' : [ 0x2f4, ['unsigned short']],
  'GdtR0Data' : [ 0x2f6, ['unsigned short']],
  'GdtR0Pcr' : [ 0x2f8, ['unsigned short']],
  'GdtR3Code' : [ 0x2fa, ['unsigned short']],
  'GdtR3Data' : [ 0x2fc, ['unsigned short']],
  'GdtR3Teb' : [ 0x2fe, ['unsigned short']],
  'GdtLdt' : [ 0x300, ['unsigned short']],
  'GdtTss' : [ 0x302, ['unsigned short']],
  'Gdt64R3CmCode' : [ 0x304, ['unsigned short']],
  'Gdt64R3CmTeb' : [ 0x306, ['unsigned short']],
  'IopNumTriageDumpDataBlocks' : [ 0x308, ['unsigned long long']],
  'IopTriageDumpDataBlocks' : [ 0x310, ['unsigned long long']],
  'VfCrashDataBlock' : [ 0x318, ['unsigned long long']],
  'MmBadPagesDetected' : [ 0x320, ['unsigned long long']],
  'MmZeroedPageSingleBitErrorsDetected' : [ 0x328, ['unsigned long long']],
  'EtwpDebuggerData' : [ 0x330, ['unsigned long long']],
  'OffsetPrcbContext' : [ 0x338, ['unsigned short']],
} ],
}