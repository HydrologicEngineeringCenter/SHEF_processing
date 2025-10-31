import logging
import sys
from datetime import datetime
from io import BufferedRandom, StringIO
from typing import Optional, TextIO, Union
from abc import ABC, abstractmethod

import cwms

from shef import loaders
from shef.loaders import shared

version = "1.0.0"
version_date = "31Oct2025"


class BaseExporter (ABC):
    """
    Base class for SHEF exporters

    Loaders that support unloading expect to read a loader-specific time series format from their inputs when unloading.

    Exporters provide the means to select time series data to present to the loaders for unloading. Selecting includes:
    * Specifying a time window
    * Specifying time series identifiers in loader-specific formats
    """

    def __init__(self):
        """
        Initializer for BaseExporter class
        """
        logging.basicConfig(
            stream=sys.stderr, format="%(levelname)s: %(msg)s", level=logging.WARNING
        )
        self._logger = logging.getLogger(self.__class__.__name__)
        self._output: Optional[Union[BufferedRandom, TextIO, StringIO]] = sys.stdout
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    @property
    def end_time(self) -> Optional[datetime]:
        """
        The end of the time window to export

        Oprations:
            Read/Write
        """
        return self._end_time

    @end_time.setter
    def end_time(self, value: Optional[datetime]) -> None:
        self._end_time = value

    @abstractmethod
    def export(self, identifier: str) -> None:
        """
        Exports SHEF text for the the specified identifier for the current time window to the current export output stream

        Args:
            identifier (str): The identifier (time series ID, group ID, etc...)
        """

    def set_output(
        self,
        output_object: Optional[Union[BufferedRandom, TextIO, StringIO]],
    ) -> None:
        """
        Sets the output stream for subsequent exports. All exports go to the system standard output device (sys.stdout)
        unless redirected by this call.

        Notably this can be set to a StringIO object in order to capture the output for further processing

        Example:
            ```
            exporter = CdaExporter(api_root, api_key, office)
            exporter.start_time = start_time
            exporter.end_time = end_time
            with StringIO() as buf:
                exporter.set_output(buf)
                exporter.export(tsid)
                export_data = buf.getvalue()
            # work with export_data as desired
            ```
        Args:
            output_object (Optional[Union[BufferedRandom, TextIO, StringIO]]): A file-like object to use as the export output stream
        """
        self._output = output_object

    @property
    def start_time(self) -> Optional[datetime]:
        """
        The start of the time window to export

        Oprations:
            Read/Write
        """
        return self._start_time

    @start_time.setter
    def start_time(self, value: Optional[datetime]) -> None:
        self._start_time = value
