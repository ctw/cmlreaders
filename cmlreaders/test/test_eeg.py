import json
from pathlib import Path
from pkg_resources import resource_filename
import pytest

from cmlreaders import CMLReader, PathFinder
from cmlreaders.readers.eeg import events_to_epochs, SplitEEGReader


@pytest.fixture
def events():
    cml_reader = CMLReader()
    path = resource_filename('cmlreaders.test.data', 'all_events.json')
    reader = cml_reader.get_reader('events', file_path=path)
    return reader.as_dataframe()


@pytest.mark.parametrize('rel_start', [-100, 0])
@pytest.mark.parametrize('rel_stop', [100, 500])
def test_events_to_epochs(events, rel_start, rel_stop):
    words = events[events.type == 'WORD']

    epochs = events_to_epochs(words, rel_start=rel_start, rel_stop=rel_stop)
    assert len(epochs) == 156
    for epoch in epochs:
        assert epoch[1] - epoch[0] == rel_stop - rel_start


@pytest.mark.rhino
class TestFileReaders:
    def get_finder(self, subject, experiment, session, rootdir):
        return PathFinder(subject, experiment, session, rootdir=rootdir)

    def test_split_eeg_reader(self, rhino_root):
        finder = self.get_finder('R1111M', 'FR1', 0, rhino_root)
        meta_path = Path(finder.find('sources'))
        with meta_path.open() as metafile:
            meta = list(json.load(metafile).values())[0]

        basename = meta['name']
        sample_rate = meta['sample_rate']
        dtype = meta['data_format']
        filename = str(meta_path.parent.joinpath('noreref', basename))

        starts = range(0, 500, 100)
        stops = [start + 200 for start in starts]
        epochs = list(zip(starts, stops))
        eeg_reader = SplitEEGReader(filename, sample_rate, dtype, epochs)
        ts = eeg_reader.read()
        assert ts.shape == (len(epochs), 100, 200)
