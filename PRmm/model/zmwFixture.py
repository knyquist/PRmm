import numpy as np
from functools import wraps

from PRmm.model import Region, MultiAlignment

def cached(f):
    """
    Decorator that lets us memoize the return value of a nullary
    function call in an object-local cache.
    """
    @wraps(f)
    def g(self):
        if not hasattr(self, "_cache"):
            self._cache = {}
        if f.__name__ not in self._cache:
            self._cache[f.__name__] = f(self)
        else:
            print "Cache hit!"
        return self._cache[f.__name__]
    return g

class Unimplemented(Exception): pass
class Unavailable(Exception): pass


class ZmwFixture(object):
    """
    A ZMW fixture provides a ZMW level view of the world---access to
    data from a single ZMW, collating the different data types (trace,
    pulse, base, alignment).

    It provides a facade over the different BAM/HDF5 data files that
    might be providing base, pulse, and alignment data.  While
    minimal, this facade is sufficient for PRmm's purposes.
    """
    def __init__(self, readersFixture, holeNumber):
        self.readers = readersFixture
        self.holeNumber = holeNumber
        self._pulses = self.readers.plsF[holeNumber].pulses()  if self.readers.hasPulses else None
        self._bases = self.readers.basF[holeNumber].readNoQC() if self.readers.hasBases  else None
        if self.readers.hasAlignments:
            self._alns = self.readers.alnF.readsByHoleNumber(holeNumber)
        else:
            self._alns = []

    # -- Identifying info --

    @property
    def zmwName(self):
        return "%s/%d" % (self.readers.movieName, self.holeNumber)

    # -- Trace info --

    @property
    def cameraTrace(self):
        return self.readers.trcF[self.holeNumber]

    @property
    def dwsTrace(self):
        raise Unimplemented()

    # -- Pulsecall info --

    @property
    def hasPulses(self):
        return self._pulses is not None

    @property
    def numPulses(self):
        return len(self._pulses)

    @property
    def pulseLabel(self):
        return self._pulses.channelBases()

    @property
    def pulseStartFrame(self):
        return self._pulses.startFrame()

    @property
    def pulseEndFrame(self):
        return self._pulses.endFrame()

    @property
    def pulsePkmid(self):
        return self._pulses.midSignal()

    @property
    def pulsePkmean(self):
        return self._pulses.meanSignal()

    @property
    def pulseIsBase(self):
        ans = np.zeros(self.numPulses, dtype=bool)
        ans[self.basePulseIndex] = True
        return ans

    # -- Basecall info --

    @property
    def hasBases(self):
        return self._bases is not None

    @property
    def baseLabel(self):
        return self._bases.basecalls()

    @property
    @cached
    def baseStartFrame(self):
        return self.pulseStartFrame[self.basePulseIndex]

    @property
    @cached
    def baseEndFrame(self):
        return self.pulseEndFrame[self.basePulseIndex]

    @property
    def basePulseIndex(self):
        return self._bases.PulseIndex()


    # -- Alignment info ---

    @property
    def hasAlignments(self):
        return bool(self._alns)

    @property
    def multiAlignment(self):
        return MultiAlignment.fromAlnHits(self.baseLabel, self._alns)

    # -- Regions info --

    @property
    def regions(self):
        """
        Get region info---FRAME delimited
        """
        if (not self.hasPulses or not self.hasBases):
            raise Unavailable, "Pulses and bases are required to access regions"
        else:
            ans = []
            for basRegion in self._bases.zmw.regionTable:
                startFrame = self.baseStartFrame[basRegion.regionStart]
                endFrame = self.baseEndFrame[basRegion.regionEnd-1] # TODO: check this logic
                ans.append(Region(basRegion.regionType, startFrame, endFrame))
            # Are there alignments?
            if self.hasAlignments:
                for aln in self._alns:
                    ans.append(Region(Region.ALIGNMENT_REGION,
                                 self.baseStartFrame[aln.rStart],
                                 self.baseEndFrame[aln.rEnd-1]))
            return sorted(ans)

    # -- Interval queries --
