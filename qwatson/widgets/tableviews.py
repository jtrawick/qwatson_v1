# -*- coding: utf-8 -*-

# Copyright © 2018 Jean-Sébastien Gosselin
# https://github.com/jnsebgosselin/qwatson
#
# This file is part of QWatson.
# Licensed under the terms of the GNU General Public License.

# ---- Standard imports

import sys
from math import ceil

# ---- Third party imports

import arrow
from PyQt5.QtCore import pyqtSignal as QSignal
from PyQt5.QtCore import Qt, QPoint, QModelIndex
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QApplication, QGridLayout, QHeaderView, QLabel, QMessageBox, QScrollArea,
    QTableView, QHBoxLayout, QVBoxLayout, QWidget, QFrame)

# ---- Local imports

from qwatson.utils import icons
from qwatson.utils.dates import arrowspan_to_str, total_seconds_to_hour_min
from qwatson.watson_ext.watsonhelpers import find_where_to_insert_new_frame
from qwatson.widgets.layout import ColoredFrame
from qwatson.widgets.toolbar import QToolButtonBase
from qwatson.widgets.dates import DateRangeNavigator
from qwatson.models.tablemodels import WatsonSortFilterProxyModel
from qwatson.models.delegates import (
    BaseDelegate, ToolButtonDelegate, ComboBoxDelegate, LineEditDelegate,
    DateTimeDelegate, TagEditDelegate)


class ActivityOverviewWidget(QWidget):
    """A widget to show and edit activities logged with Watson."""
    def __init__(self, model, parent=None):
        super(ActivityOverviewWidget, self).__init__(parent)
        self.setWindowIcon(icons.get_icon('master'))
        self.setWindowTitle("Activity Overview")

        self.model = model

        self.setup(model)
        self.date_span_changed()

    def setup(self, model):
        """Setup the widget with the provided arguments."""
        self.table_widg = WatsonMultiTableWidget(model, parent=self)
        self.toolbar = self.setup_toolbar()

        # ---- Setup the layout

        layout = QGridLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.table_widg)

    def setup_toolbar(self):
        """Setup the toolbar of the widget."""
        self.date_range_nav = DateRangeNavigator()
        self.date_range_nav.sig_date_span_changed.connect(
            self.date_span_changed)

        self.add_act_above_btn = QToolButtonBase('insert_above', 'small')
        self.add_act_above_btn.setToolTip(
            "<b>Add Activity Above</b><br><br>"
            "Add a new activity directly above the currently selected"
            " activity. If no activity is selected, the new activity will"
            " be added at the beginning of the week.")
        self.add_act_above_btn.clicked.connect(
            lambda: self.table_widg.add_new_activity('above'))

        self.add_act_below_btn = QToolButtonBase('insert_below', 'small')
        self.add_act_below_btn.setToolTip(
            "<b>Add Activity Below</b><br><br>"
            "Add a new activity directly below the currently selected"
            " activity. If no activity is selected, the new activity will"
            " be added at the end of the week.")
        self.add_act_below_btn.clicked.connect(
            lambda: self.table_widg.add_new_activity('below'))

        # Setup the layout.

        toolbar = QFrame()

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        layout.addWidget(self.date_range_nav)
        layout.addStretch()
        layout.addWidget(self.add_act_above_btn)
        layout.addWidget(self.add_act_below_btn)

        return toolbar

    def date_span_changed(self):
        """Handle when the range of the date range navigator widget change."""
        self.table_widg.set_date_span(self.date_range_nav.current)

    def show(self):
        """Qt method override."""
        super(ActivityOverviewWidget, self).show()
        if self.windowState() & Qt.WindowMaximized:
            self.setWindowState(Qt.WindowActive | Qt.WindowMaximized)
        else:
            self.setWindowState(Qt.WindowActive)
        self.activateWindow()
        self.raise_()
        self.setFocus()


# ---- TableWidget

class WatsonMultiTableWidget(QFrame):
    """
    A widget that displays Watson activities on a daily basis over a
    given timespan.
    """

    def __init__(self, model, date_span=arrow.now().floor('week').span('week'),
                 parent=None):
        super(WatsonMultiTableWidget, self).__init__(parent)

        self.total_seconds = 0
        self.date_span = date_span
        self.model = model
        self.model.sig_total_seconds_changed.connect(self.setup_time_total)
        self.tables = []
        self.last_focused_table = None

        self.setup()
        self.set_date_span(date_span)

    def setup(self):
        """Setup the widget with the provided arguments."""
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.scrollarea = self.setup_scrollarea()
        layout.addWidget(self.scrollarea, 0, 0)

        statusbar = self.setup_satusbar()
        layout.addWidget(statusbar, 1, 0)

    def setup_scrollarea(self):
        """Setup the scrollarea that holds all the table widgets."""
        scrollarea = QScrollArea()
        scrollarea.verticalScrollBar().valueChanged.connect(
            self.srollbar_value_changed)

        widget = ColoredFrame(color='light')

        self.scene = QVBoxLayout(widget)
        self.scene.addStretch(100)
        self.scene.setSpacing(5)
        self.scene.setContentsMargins(10, 5, 10, 5)

        scrollarea.setMinimumWidth(900)
        scrollarea.setMinimumHeight(500)
        scrollarea.setWidget(widget)
        scrollarea.setWidgetResizable(True)

        return scrollarea

    def setup_satusbar(self):
        """Setup the statusbar of the table."""
        self.total_time_labl = QLabel()
        self.total_time_labl.setAlignment(Qt.AlignRight)

        font = self.total_time_labl.font()
        font.setBold(True)
        self.total_time_labl.setFont(font)

        return self.total_time_labl

    def set_date_span(self, date_span):
        """
        Set the range over which activities are displayed in the widget
        and update the layout accordingly by adding or removing tables.
        """
        self.clear_focused_table()
        self.date_span = date_span
        total_seconds = round((date_span[1] - date_span[0]).total_seconds())
        ndays = ceil(total_seconds / (60*60*24))
        while True:
            if len(self.tables) == ndays:
                break
            elif len(self.tables) < ndays:
                self.tables.append(WatsonTableWidget(self.model, parent=self))
                self.tables[-1].sig_tableview_focused_in.connect(
                    self.tableview_focused_in)
                self.tables[-1].sig_tableview_cleared.connect(
                    self.tableview_cleared)
                self.scene.insertWidget(self.scene.count()-1, self.tables[-1])
            else:
                self.tables.remove(self.tables[-1])
                self.scene.removeWidget(self.tables[-1])
                self.tables[-1].deleteLater()

        # We hide the scrollbar widget while the tables are ubdated
        # to avoid flickering.
        self.scrollarea.widget().hide()
        base_span = date_span[0].span('day')
        for i, table in enumerate(self.tables):
            table.set_date_span(
                (base_span[0].shift(days=i), base_span[1].shift(days=i)))
        self.scrollarea.widget().show()

    def setup_time_total(self, delta_seconds):
        """
        Setup the total amount of time for all the activities listed
        for the date span.
        """
        self.total_seconds = self.total_seconds + delta_seconds
        self.total_time_labl.setText(
            "Total : %s" % total_seconds_to_hour_min(self.total_seconds))

    # ---- Table focus handlers

    def tableview_focused_in(self, table):
        """
        Save the last focused table and unselect the previous focused table.
        """
        if self.last_focused_table != table:
            self.clear_focused_table()
            table.view.set_selected(True)
            self.last_focused_table = table

    def tableview_cleared(self, table):
        """
        Handle when one of the tables is now empty due to the user deleting
        one or more of its activities.
        """
        if table == self.last_focused_table:
            self.clear_focused_table()

    def clear_focused_table(self):
        """Clear the last focused table."""
        if self.last_focused_table is not None:
            self.last_focused_table.view.set_selected(False)
        self.last_focused_table = None

    def srollbar_value_changed(self, value):
        """
        Handle when the value of the vertical scrollbar changes, so that
        the mouse hovered highlighted row can be updated correctly.
        """
        viewport = self.scrollarea.viewport()
        mouse_pos = viewport.mapFromGlobal(QCursor.pos()) + QPoint(0, value)
        # We add the scrollbar value so that we get the mouse cursor
        # vertical position relative to the widget of the scrollarea
        # instead of the viewport.
        for table in self.tables:
            # Get the mouse position relative to the table view of the
            # corresponding widget.
            view_mouse_pos = mouse_pos - table.pos() - table.view.pos()

            if not table.view.rect().contains(view_mouse_pos):
                row_at = None
            else:
                row_at = table.view.rowAt(view_mouse_pos.y())
            table.view.set_hovered_row(row_at)

    def add_new_activity(self, where='above'):
        """
        Add a new activity in the last focused table if not None. If the last
        focused table is None, the activity is added to the first table of the
        page if where is 'above' or to the last table if where is 'below'.
        """
        if self.last_focused_table is not None and self.last_focused_table:
            frame_index = self.last_focused_table.get_selected_frame_index()
            if where == 'above':
                insert_time = self.model.client.frames[frame_index].start
            elif where == 'below':
                insert_time = self.model.client.frames[frame_index].stop
                frame_index += 1
        elif where == 'above':
            frame_index = find_where_to_insert_new_frame(
                self.model.client, self.tables[0].date_span[0], where)
            insert_time = self.tables[0].date_span[0]
        elif where == 'below':
            frame_index = find_where_to_insert_new_frame(
                self.model.client, self.tables[-1].date_span[1], where)
            insert_time = self.tables[-1].date_span[1]

        self.model.beginInsertRows(QModelIndex(), frame_index, frame_index)
        self.model.client.insert(
            project='', start=insert_time, stop=insert_time,
            message=("<New activity added manually on %s>" %
                     arrow.now().format('YYYY-MM-DD HH:mm'))
            )
        self.model.client.save()
        self.model.endInsertRows()


class WatsonTableWidget(QWidget):
    """
    A widget that contains a formatted table view and a custom title bar
    that shows the date span and the time count of all the activities listed
    in the table.
    """
    sig_tableview_focused_in = QSignal(object)
    sig_tableview_cleared = QSignal(object)

    def __init__(self, model, parent=None):
        super(WatsonTableWidget, self).__init__(parent)
        self.view = FormatedWatsonTableView(model)
        titlebar = self.setup_titlebar()

        layout = QGridLayout(self)
        layout.addWidget(titlebar, 0, 0)
        layout.addWidget(self.view, 1, 0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view.proxy_model.sig_total_seconds_changed.connect(
            self.setup_timecount)
        self.view.sig_focused_in.connect(
            lambda: self.sig_tableview_focused_in.emit(self))
        self.view.sig_table_cleared.connect(
            lambda: self.sig_tableview_cleared.emit(self))

    def setup_titlebar(self):
        """Setup the titlebar of the table."""
        font = QLabel().font()
        font.setBold(True)

        self.title = QLabel()
        self.title.setMargin(5)
        self.title.setFont(font)

        self.timecount = QLabel()
        self.timecount.setMargin(5)
        self.timecount.setFont(font)

        titlebar = ColoredFrame(color='grey')
        titlebar_layout = QHBoxLayout(titlebar)
        titlebar_layout.setContentsMargins(0, 0, 0, 0)

        titlebar_layout.addWidget(self.title)
        titlebar_layout.addStretch(100)
        titlebar_layout.addWidget(self.timecount)

        return titlebar

    @property
    def date_span(self):
        """Return the arrow span of the filter proxy model."""
        return self.view.proxy_model.date_span

    def set_date_span(self, date_span):
        """Set the date span in the table and title."""
        self.view.set_date_span(date_span)
        self.title.setText(arrowspan_to_str(date_span))

    def setup_timecount(self, total_seconds):
        """
        Setup the time count for the activities of the table in the titlebar.
        """
        self.timecount.setText(total_seconds_to_hour_min(total_seconds))

    def get_selected_row(self):
        """Return the index of the selected row in the view."""
        return self.view.get_selected_row()

    def get_selected_frame_index(self):
        """
        Return the index of the frame corresponding to the selected row if
        there is one, else return None.
        """
        return self.view.get_selected_frame_index()


# ---- TableView

class BasicWatsonTableView(QTableView):
    """
    A single table view that displays Watson activity log and
    allow sorting and filtering of the data through the use of a proxy model.
    """
    sig_table_cleared = QSignal(object)

    def __init__(self, source_model, parent=None):
        super(BasicWatsonTableView, self).__init__(parent)
        self.setSortingEnabled(False)

        self.proxy_model = WatsonSortFilterProxyModel(source_model)
        self.setModel(self.proxy_model)
        self.proxy_model.sig_btn_delrow_clicked.connect(self.del_model_row)

        # ---- Setup the delegates

        columns = source_model.COLUMNS
        self.setItemDelegateForColumn(
            columns['icons'], ToolButtonDelegate(self))
        self.setItemDelegateForColumn(
            columns['project'], ComboBoxDelegate(self))
        self.setItemDelegateForColumn(
            columns['comment'], LineEditDelegate(self))
        self.setItemDelegateForColumn(columns['start'], DateTimeDelegate(self))
        self.setItemDelegateForColumn(columns['end'], DateTimeDelegate(self))
        self.setItemDelegateForColumn(columns['tags'], TagEditDelegate(self))
        self.setItemDelegateForColumn(columns['duration'], BaseDelegate(self))
        self.setItemDelegateForColumn(columns['id'], BaseDelegate(self))

        # ---- Setup column size

        self.setColumnWidth(columns['tags'],
                            1.5 * self.horizontalHeader().defaultSectionSize())
        self.setColumnWidth(columns['icons'],
                            icons.get_iconsize('small').width() + 12)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(
            columns['comment'], QHeaderView.Stretch)

    def del_model_row(self, proxy_index):
        """
        Ask for confirmation to delete a row and delete or not the row from
        the model according the answer.
        """
        frame_id = self.proxy_model.get_frameid_from_index(proxy_index)
        ans = QMessageBox.question(
            self, 'Delete frame', "Do you want to delete frame %s?" % frame_id,
            defaultButton=QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.proxy_model.removeRows(proxy_index)
            if self.proxy_model.get_accepted_row_count() == 0:
                self.sig_table_cleared.emit(self)

    def set_date_span(self, date_span):
        """Set the date span in the proxy model."""
        self.proxy_model.set_date_span(date_span)

    def focusInEvent(self, event):
        """Qt method override."""
        self.sig_focused_in.emit(self)
        super(BasicWatsonTableView, self).focusInEvent(event)


class FormatedWatsonTableView(BasicWatsonTableView):
    """
    A BasicWatsonTableView formatted to look good when put in a scrollarea
    in a vertical stack of tables.
    """
    sig_focused_in = QSignal(object)
    _hovered_row = None

    def __init__(self, source_model, parent=None):
        super(FormatedWatsonTableView, self).__init__(source_model, parent)
        self.setup()
        self.update_table_height()
        self.entered.connect(self.itemEnterEvent)

    def setup(self):
        """Setup the table view with the provided arguments."""
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setWordWrap(False)

        self.setMouseTracking(True)
        self.setSelectionBehavior(self.SelectRows)
        self.setSelectionMode(self.SingleSelection)
        self.set_selected(False)

        self.horizontalHeader().hide()
        self.verticalHeader().hide()

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.proxy_model.sig_sourcemodel_changed.connect(
            self.update_table_height)

    def update_table_height(self):
        """
        Update the height of the table to fit all the data, so that there is
        no need for a vertical scrollbar.
        """
        self.setFixedHeight(self.get_min_height())

    def get_min_height(self):
        """Calculate the height of the table content."""
        h = 2 * self.frameWidth()
        for i in range(self.model().get_accepted_row_count()):
            h += self.rowHeight(i)
        return h

    def set_date_span(self, date_span):
        """
        Method override to update table height when setting the date span.
        """
        super(FormatedWatsonTableView, self).set_date_span(date_span)
        self.update_table_height()

    # ---- Row selection

    def set_selected(self, value):
        self.is_selected = bool(value)
        self.viewport().update()

    def get_selected_row(self):
        """
        Return the index of the selected row if there is one and return
        None otherwise.
        """
        if self.is_selected:
            return self.selectionModel().selectedRows()[0].row()
        else:
            return None

    def get_selected_frame_index(self):
        """
        Return the index of the frame corresponding to the selected row if
        there is one, else return None.
        """
        if self.is_selected:
            selected_row = self.selectionModel().selectedRows()
            if len(selected_row) > 0:
                return self.proxy_model.mapToSource(selected_row[0]).row()
        return None

    # ---- Mouse hovered

    def set_hovered_row(self, row):
        if self._hovered_row != row:
            self._hovered_row = row
            self.viewport().update()

    def itemEnterEvent(self, index):
        self.set_hovered_row(index.row())

    def leaveEvent(self, event):
        super(FormatedWatsonTableView, self).leaveEvent(event)
        self.set_hovered_row(None)

    def focusOutEvent(self, event):
        super(FormatedWatsonTableView, self).focusOutEvent(event)
        self.set_hovered_row(None)


if __name__ == '__main__':
    from qwatson.watson_ext.watsonextends import Watson
    from qwatson.models.tablemodels import WatsonTableModel
    import os.path as osp
    from qwatson import __rootdir__

    dirname = osp.join(__rootdir__, 'widgets', 'tests', 'appdir')
    client = Watson(config_dir=dirname)
    model = WatsonTableModel(client)

    app = QApplication(sys.argv)

    from PyQt5.QtWidgets import QStyleFactory
    app.setStyle(QStyleFactory.create('WindowsVista'))

    overview_window = ActivityOverviewWidget(model)
    overview_window.show()
    app.exec_()
