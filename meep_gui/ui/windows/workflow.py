from __future__ import annotations

from PyQt5 import QtWidgets

from ...store import ProjectStore
from ..tabs import (
    AnalysisTab,
    DomainTab,
    FluxMonitorsTab,
    GeometryTab,
    MaterialsTab,
    ParametersTab,
    ScriptTab,
    SourcesTab,
    SweepTab,
)
from .base import QuitOnCloseWindow


class WorkflowWindow(QuitOnCloseWindow):
    def __init__(self, store: ProjectStore) -> None:
        super().__init__()
        self.setWindowTitle("Meep GUI - Workflow")
        self.resize(900, 700)
        self.setMinimumSize(600, 400)

        tabs = QtWidgets.QTabWidget()
        tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        tabs.addTab(ParametersTab(store), "Parameters")
        tabs.addTab(DomainTab(store), "Domain")
        tabs.addTab(MaterialsTab(store), "Materials")
        tabs.addTab(GeometryTab(store), "Geometry")
        tabs.addTab(SourcesTab(store), "Sources")
        tabs.addTab(FluxMonitorsTab(store), "Monitors")
        tabs.addTab(SweepTab(store), "Sweep")
        tabs.addTab(AnalysisTab(store), "Analysis")
        tabs.addTab(ScriptTab(store), "Script")

        self.setCentralWidget(tabs)
