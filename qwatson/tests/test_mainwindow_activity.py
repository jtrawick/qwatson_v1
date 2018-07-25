# -*- coding: utf-8 -*-

# Copyright © 2018 Jean-Sébastien Gosselin
# https://github.com/jnsebgosselin/qwatson
#
# This file is part of QWatson.
# Licensed under the terms of the GNU General Public License.

# ---- Standard imports

import os
import os.path as osp
import json

# ---- Third party imports

import arrow
import pytest
from PyQt5.QtCore import Qt

# ---- Local imports

from qwatson.mainwindow import QWatson
from qwatson.utils.dates import local_arrow_from_tuple
from qwatson.utils.fileio import delete_folder_recursively


@pytest.fixture(scope="module")
def now():
    return local_arrow_from_tuple((2018, 7, 25, 6, 0, 0))


@pytest.fixture(scope="module")
def appdir(tmpdir_factory, now):
    appdir = osp.join(osp.dirname(__file__), 'appdir4')
    delete_folder_recursively(appdir, delroot=True)
    os.mkdir(appdir)

    # Create the projects file.
    with open(osp.join(appdir, 'projects'), 'w') as f:
        f.write(json.dumps(['p1', 'p2', 'p3']))

    # Create the frames file.
    frames = [[now.timestamp, now.timestamp, "p1",
               "e22fe653844442bab09a109f086688ec",
               ["tag1", "tag2", "tag3"], now.timestamp, "Base activity"]]
    with open(osp.join(appdir, 'frames'), 'w') as f:
        f.write(json.dumps(frames))

    return appdir


@pytest.fixture
def qwatson_creator(qtbot, mocker, appdir, now):
    mocker.patch('arrow.now', return_value=now)
    qwatson = QWatson(config_dir=appdir)
    qtbot.addWidget(qwatson)

    # Add one activity to frames.

    qwatson.show()
    qtbot.waitForWindowShown(qwatson)

    qtbot.addWidget(qwatson.overview_widg)
    qtbot.mouseClick(qwatson.btn_report, Qt.LeftButton)
    qtbot.waitForWindowShown(qwatson.overview_widg)

    yield qwatson, qtbot, mocker
    qwatson.close()


# ---- Test QWatsonActivityMixin

def test_setup(qwatson_creator):
    """Test that the projects and frames files were generated correctly."""
    qwatson, qtbot, mocker = qwatson_creator

    assert qwatson.client.projects == ['', 'p1', 'p2', 'p3']
    assert len(qwatson.client.frames) == 1
    assert qwatson.currentProject() == 'p1'
    assert qwatson.tag_manager.tags == ['tag1', 'tag2', 'tag3']
    assert qwatson.comment_manager.text() == 'Base activity'

    overview = qwatson.overview_widg
    assert overview.hasFocus()
    assert overview.table_widg.last_focused_table is None

    row_counts = [table.rowCount() for table in overview.table_widg.tables]
    assert row_counts == [0, 0, 1, 0, 0, 0, 0]


def test_add_activity_below_nofocus(qwatson_creator):
    """
    Test that adding an activity below when no row is selected in the overview
    table works as expected.
    """
    qwatson, qtbot, mocker = qwatson_creator
    overview = qwatson.overview_widg

    qwatson.comment_manager.setText('Add activity below, no focus')
    qtbot.mouseClick(overview.add_act_below_btn, Qt.LeftButton)

    # Assert the that the frame was added correctly.

    frames = qwatson.client.frames
    assert len(frames) == 2
    frame = frames[1]
    assert frame.start == frame.stop == arrow.now().floor('week').shift(days=6)
    assert frame.project == 'p1'
    assert frame.message == 'Add activity below, no focus'
    assert frame.tags == ['tag1', 'tag2', 'tag3']

    # Assert that the overview table is showing the right thing.

    row_counts = [table.rowCount() for table in overview.table_widg.tables]
    assert row_counts == [0, 0, 1, 0, 0, 0, 1]


def test_add_activity_above_nofocus(qwatson_creator):
    """
    Test that adding an activity above when no row is selected in the overview
    table works as expected.
    """
    qwatson, qtbot, mocker = qwatson_creator
    overview = qwatson.overview_widg

    qwatson.comment_manager.setText('Add activity above, no focus')
    qwatson.setCurrentProject('p2')
    qtbot.mouseClick(overview.add_act_above_btn, Qt.LeftButton)

    # Assert the that the frame was added correctly.

    frames = qwatson.client.frames
    assert len(frames) == 3
    frame = frames[0]
    assert frame.start == frame.stop == arrow.now().floor('week')
    assert frame.project == 'p2'
    assert frame.message == 'Add activity above, no focus'

    # Assert that the overview table is showing the right thing.

    row_counts = [table.rowCount() for table in overview.table_widg.tables]
    assert row_counts == [1, 0, 1, 0, 0, 0, 1]


def test_add_activity_above_selection(qwatson_creator):
    """
    Test that adding an activity above the selected row in the overview table
    works as expected.
    """
    qwatson, qtbot, mocker = qwatson_creator
    overview = qwatson.overview_widg

    qwatson.comment_manager.setText('Add activity above selection')

    # Select the base activity and add a new activity above.

    table = overview.table_widg.tables[2]
    index = table.view.proxy_model.index(0, 0)
    visual_rect = table.view.visualRect(index)

    qtbot.mouseClick(
        table.view.viewport(), Qt.LeftButton, pos=visual_rect.center())

    assert table.get_selected_row() == 0

    # Add an activity above the selection.

    qtbot.mouseClick(overview.add_act_above_btn, Qt.LeftButton)

    # Assert the that the frame was added correctly.

    frames = qwatson.client.frames
    assert len(frames) == 4
    frame = frames[1]
    assert frame.start == frame.stop == arrow.now()
    assert frame.message == 'Add activity above selection'

    # Assert that the overview table is showing the right thing.

    row_counts = [table.rowCount() for table in overview.table_widg.tables]
    assert row_counts == [1, 0, 2, 0, 0, 0, 1]
    assert table.get_selected_row() == 1


def test_add_activity_below_selection(qwatson_creator):
    """
    Test that adding an activity below the selected row in the overview table
    works as expected.
    """
    qwatson, qtbot, mocker = qwatson_creator
    overview = qwatson.overview_widg

    qwatson.comment_manager.setText('Add activity below selection')

    # Select the base activity and add a new activity below.

    table = overview.table_widg.tables[2]
    index = table.view.proxy_model.index(1, 0)
    visual_rect = table.view.visualRect(index)

    qtbot.mouseClick(
        table.view.viewport(), Qt.LeftButton, pos=visual_rect.center())

    assert table.get_selected_row() == 1

    # Add an activity below the selection.

    qtbot.mouseClick(overview.add_act_below_btn, Qt.LeftButton)

    # Assert the that the frame was added correctly.

    frames = qwatson.client.frames
    assert len(frames) == 5
    frame = frames[3]
    assert frame.start == frame.stop == arrow.now()
    assert frame.message == 'Add activity below selection'

    # Assert that the overview table is showing the right thing.

    row_counts = [table.rowCount() for table in overview.table_widg.tables]
    assert row_counts == [1, 0, 3, 0, 0, 0, 1]
    assert table.get_selected_row() == 1


if __name__ == "__main__":
    pytest.main(['-x', os.path.basename(__file__), '-v', '-rw'])
