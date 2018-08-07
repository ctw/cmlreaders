import functools
from pkg_resources import resource_filename
import pytest
from unittest.mock import patch

import numpy as np
import pandas as pd

from cmlreaders.exc import UnsupportedRepresentation, UnsupportedExperimentError
from cmlreaders.readers.readers import (
    BaseJSONReader,
    ClassifierContainerReader,
    EventReader,
    TextReader,
    RAMCSVReader,
    RamulatorEventLogReader,
)
from cmlreaders.readers.electrodes import (
    ElectrodeCategoriesReader,
    LocalizationReader,
    MontageReader
)
from cmlreaders.readers.reports import (
    BaseRAMReportDataReader,
    RAMReportSummaryDataReader
)

datafile = functools.partial(resource_filename, 'cmlreaders.test.data')


class TestTextReader:
    @pytest.mark.parametrize("method", ['dataframe', 'recarray', 'dict'])
    @pytest.mark.parametrize("data_type", [
        "voxel_coordinates", "leads", "classifier_excluded_leads", "good_leads",
        "jacksheet", "area"])
    @pytest.mark.parametrize("subject,localization", [
        ('R1389J', '0'),
    ])
    def test_as_methods(self, method, data_type, subject, localization):
        file_path = datafile(data_type + ".txt")
        reader = TextReader(data_type, subject, localization=localization,
                            file_path=file_path)
        expected_types = {
            'dataframe': pd.DataFrame,
            'recarray': np.recarray,
            'dict': list
        }
        method_name = "as_{}".format(method)
        callable_method = getattr(reader, method_name)
        data = callable_method()
        assert data is not None
        assert type(data) == expected_types[method]

    @pytest.mark.parametrize("subject,filename,sep", [
        ("R1389J", datafile("jacksheet.txt"), " "),
        ("R1406M", datafile("R1406M_jacksheet.txt"), "\t"),
    ])
    def test_read_jacksheet(self, subject, filename, sep):
        js = TextReader.fromfile(filename, subject=subject, data_type="jacksheet")

        assert "number" in js.columns
        assert "label" in js.columns

        data = np.loadtxt(filename, delimiter=sep, dtype=[
            ("number", "<i8"),
            ("label", "|U32"),
        ])

        np.testing.assert_equal(data["number"], js.number)
        np.testing.assert_equal(data["label"], js.label)

    def test_failures(self):
        """
        When unable to locate a path, constructor should pass but `load()`
        should fail.
        """
        reader = TextReader('jacksheet', subject='R1XXX', localization=0)
        with pytest.raises(FileNotFoundError):
            reader.load()


class TestRAMCSVReader:
    @pytest.mark.parametrize("method", ["dataframe", "recarray", "dict"])
    @pytest.mark.parametrize("data_type", [
        'electrode_coordinates', 'prior_stim_results', 'target_selection_table'
    ])
    @pytest.mark.parametrize("subject,localization", [
        ('R1409D', '0'),
    ])
    def test_as_methods(self, method, data_type, subject, localization):
        file_path = datafile(data_type + ".csv")
        reader = RAMCSVReader(data_type, subject, localization,
                              experiment="FR1", file_path=file_path)
        expected_types = {
            'dataframe': pd.DataFrame,
            'recarray': np.recarray,
            'dict': list
        }
        method_name = "as_{}".format(method)
        callable_method = getattr(reader, method_name)
        data = callable_method()
        assert data is not None
        assert type(data) == expected_types[method]


class TestRamulatorEventLogReader:
    @pytest.mark.parametrize("method", ["dataframe", "recarray", "dict"])
    @pytest.mark.parametrize("data_type", ['event_log'])
    @pytest.mark.parametrize("subject,experiment,session", [
        ('R1409D', 'catFR1', '1'),
    ])
    def test_as_methods(self, method, data_type, subject, experiment, session,
                        rhino_root):
        file_path = datafile(data_type + ".json")
        reader = RamulatorEventLogReader(data_type, subject=subject,
                                         experiment=experiment, session=session,
                                         file_path=file_path,
                                         rootdir=rhino_root)
        expected_types = {
            'dataframe': pd.DataFrame,
            'recarray': np.recarray,
            'dict': dict
        }
        method_name = "as_{}".format(method)
        callable_method = getattr(reader, method_name)
        data = callable_method()
        assert data is not None
        assert type(data) == expected_types[method]


class TestBaseJSONReader:
    def test_load(self):
        path = datafile('index.json')
        reader = BaseJSONReader('index.json', file_path=path)
        df = reader.load()
        assert isinstance(df, pd.DataFrame)


class TestEventReader:
    def test_load_json(self):
        path = datafile('all_events.json')
        reader = EventReader('all_events', file_path=path)
        df = reader.load()
        assert df.columns[0] == 'eegoffset'

    @pytest.mark.parametrize("kind", [
        "all_events", "task_events", "math_events"
    ])
    def test_load_matlab(self, kind):
        if kind in ["all_events", "task_events"]:
            filename = "TJ001_events.mat"
        else:
            filename = "TJ001_math.mat"
        path = datafile(filename)
        df = EventReader.fromfile(path)
        assert df.columns[0] == "eegoffset"
        assert "experiment" in df.columns
        assert len(df)


class TestMontageReader:
    @pytest.mark.parametrize("kind", ["contacts", "pairs"])
    @pytest.mark.parametrize("subject,localization,montage", [
        ("R1405E", 0, 0),
        ("R1006P", 0, 0),
        ("R1006P", 0, 1),
    ])
    def test_load(self, kind, subject, localization, montage):
        if montage == 0:
            path = datafile("{}_{}.json".format(subject, kind))
        else:
            path = datafile("{}_{}_{}.json".format(subject, montage, kind))

        reader = MontageReader(kind,
                               subject=subject,
                               localization=localization,
                               montage=montage,
                               file_path=path)
        df = reader.load()

        if kind == 'contacts':
            assert 'contact' in df.columns
        else:
            assert 'contact_1' in df.columns
            assert 'contact_2' in df.columns

        if montage == 0:
            filename = datafile("{}_{}.csv".format(subject, kind))
        else:
            filename = datafile("{}_{}_{}.csv".format(subject, montage, kind))

        reference = pd.read_csv(filename, index_col=0)
        assert all(reference == df)


class TestLocalizationReader:
    def test_load(self):
        path = datafile('localization.json')
        reader = LocalizationReader('localization', subject='R1405E', file_path=path)
        df = reader.load()
        assert isinstance(df, pd.DataFrame)


@pytest.mark.rhino
class TestElectrodeCategoriesReader:
    @pytest.mark.parametrize("subject,lens", [
        ("R1111M", {'soz': 9, 'interictal': 15, 'brain_lesion': 5, 'bad_channel': 6}),
        ("R1052E", {'soz': 2, 'interictal': 14, 'brain_lesion': 0, 'bad_channel': 0})
    ])
    def test_load(self, subject, lens, rhino_root):
        reader = ElectrodeCategoriesReader('electrode_categories',
                                           subject=subject,
                                           rootdir=rhino_root)
        categories = reader.load()
        for key, len_ in lens.items():
            assert len(categories[key]) == len_


@pytest.mark.skip(reason="TODO: reenable ramutils tests")
class TestBaseReportDataReader:
    @patch("ramutils.reports.summary.ClassifierSummary")
    @pytest.mark.parametrize("method", ['pyobject', 'dataframe', 'dict', 'recarray'])
    @pytest.mark.parametrize("data_type", ['classifier_summary'])
    @pytest.mark.parametrize("subject,experiment,session", [
        ('R1409D', 'catFR1', '1'),
    ])
    def test_as_methods(self, ClassifierSummary, method, data_type, subject,
                        experiment, session):
        file_path = datafile(data_type + ".h5")

        reader = BaseRAMReportDataReader(data_type, subject=subject,
                                         experiment=experiment, session=session,
                                         localization=0, file_path=file_path)

        method_name = "as_{}".format(method)
        callable_method = getattr(reader, method_name)

        if method != "pyobject":
            with pytest.raises(UnsupportedRepresentation):
                callable_method()
            return

        data = callable_method()
        assert data is not None
        assert ClassifierSummary.from_hdf.call_count == 1


@pytest.mark.skip(reason="TODO: reenable ramutils tests")
class TestReportSummaryReader:
    @pytest.mark.parametrize("method", ['pyobject', 'dataframe', 'recarray', 'dict'])
    @pytest.mark.parametrize("data_type", ["session_summary"])
    def test_as_methods(self, method, data_type):
        file_path = datafile(data_type + ".h5")

        with patch("ramutils.reports.summary.FRStimSessionSummary") as cls:
            reader = RAMReportSummaryDataReader(data_type, subject='R1409D',
                                                experiment='catFR5', session=1,
                                                localization=0, file_path=file_path)

            method_name = "as_{}".format(method)
            func = getattr(reader, method_name)
            func()
            assert cls.from_hdf.call_count == 1

    def test_load_nonstim_session(self):
        file_path = datafile('session_summary' + ".h5")
        reader = RAMReportSummaryDataReader('session_summary', subject='R1409D',
                                            experiment='catFR1', session=1,
                                            localization=0, file_path=file_path)
        with pytest.raises(UnsupportedExperimentError):
            reader.as_pyobject()


class TestClassifierContainerReader:
    @patch("classiflib.container.ClassifierContainer")
    @pytest.mark.parametrize("method", ['pyobject'])
    @pytest.mark.parametrize("data_type", [
        'baseline_classifier', 'used_classifier'])
    def test_as_methods(self, ClassifierContainer, method, data_type):
        file_path = datafile(data_type + ".zip")
        reader = ClassifierContainerReader(data_type, subject='R1389J',
                                           experiment='catFR5', session=1,
                                           localization=0, file_path=file_path)

        method_name = "as_{}".format(method)
        callable_method = getattr(reader, method_name)
        callable_method()
        assert ClassifierContainer.load.call_count == 1


@pytest.mark.parametrize("cls,path,dtype", [
    (ElectrodeCategoriesReader, datafile("electrode_categories.txt"), dict),
    (MontageReader, datafile("pairs.json"), pd.DataFrame),
    (MontageReader, datafile("contacts.json"), pd.DataFrame),
    (RamulatorEventLogReader, datafile("event_log.json"), pd.DataFrame),
])
def test_fromfile(cls, path, dtype):
    subject = "R1405E" if cls == MontageReader else None
    data = cls.fromfile(path, subject=subject)
    assert isinstance(data, dtype)
