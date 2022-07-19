import torch
from typing import Any, Set, Dict, List, Tuple
from collections import OrderedDict
from tabulate import tabulate

class ModelReportVisualizer:
    r"""
    The ModelReportVisualizer class aims to provide users a way to visualize some of the statistics
    that were generated by the ModelReport API. However, at a higher level, the class aims to provide
    some level of visualization of statistics to PyTorch in order to make it easier to parse data and
    diagnose any potential issues with data or a specific model. With respects to the visualizations,
    the ModelReportVisualizer class currently supports several methods of visualizing data.

    Supported Visualization Methods Include:
    - Table format
    - Plot format (line graph)
    - Histogram format

    For all of the existing visualization methods, there is the option to filter data based on:
    - A module fqn prefix
    - Feature [required for the plot and histogram]

    * :attr:`generated_reports` The reports generated by the ModelReport class in the structure below
        Ensure sure that features that are the same across different report contain the same name
        Ensure that objects representing the same features are the same type / dimension (where applicable)

    Note:
        Currently, the ModelReportVisualizer class supports visualization of data generated by the
        ModelReport class. However, this structure is extensible and should allow the visualization of
        other information as long as the information is structured in the following general format:

        Report Structure
        -- module_fqn [module with attached detectors]
            |
            -- feature keys [not every detector extracts same information]
                                    [same collected info has same keys, unless can be specific to detector]


    The goal behind the class is that the generated visualizations can be used in conjunction with the generated
    report for people to get a better understand of issues and what the fix might be. It is also just to provide
    a good visualization platform, since it might be hard to parse through the ModelReport returned dictionary as
    that grows in size.

    General Use Flow Expected
    1.) Initialize ModelReport object with reports of interest by passing in initialized detector objects
    2.) Prepare your model with prepare_fx
    3.) Call model_report.prepare_detailed_calibration on your model to add relavent observers
    4.) Callibrate your model with data
    5.) Call model_report.generate_report on your model to generate report and optionally remove added observers
    6.) Use output of model_report.generate_report to initialize ModelReportVisualizer instance
    7.) Use instance to view different views of data as desired, applying filters as needed

    """

    # keys for table dict
    TABLE_TENSOR_KEY = "tensor_level_info"
    TABLE_CHANNEL_KEY = "channel_level_info"

    def __init__(self, generated_reports: OrderedDict[str, Any]):
        r"""
        Initializes the ModelReportVisualizer instance with the necessary reports.

        Args:
            generated_reports (Dict[str, Any]): The reports generated by the ModelReport class
                can also be a dictionary generated in another manner, as long as format is same
        """
        self.generated_reports = generated_reports

    def get_all_unique_module_fqns(self) -> Set[str]:
        r"""
        The purpose of this method is to provide a user the set of all module_fqns so that if
        they wish to use some of the filtering capabilities of the ModelReportVisualizer class,
        they don't need to manually parse the generated_reports dictionary to get this information.

        Returns all the unique module fqns present in the reports the ModelReportVisualizer
        instance was initialized with.
        """
        # returns the keys of the ordered dict
        return set(self.generated_reports.keys())

    def get_all_unique_feature_names(self, plottable: bool) -> Set[str]:
        r"""
        The purpose of this method is to provide a user the set of all feature names so that if
        they wish to use the filtering capabilities of the generate_table_view(), or use either of
        the generate_plot_view() or generate_histogram_view(), they don't need to manually parse
        the generated_reports dictionary to get this information.

        Args:
            plottable (bool): True if the user is only looking for plottable features, False otherwise
                plottable features are those that are tensor values

        Returns all the unique module fqns present in the reports the ModelReportVisualizer
        instance was initialized with.
        """
        unique_feature_names = set()
        for module_fqn in self.generated_reports:
            # get dict of the features
            feature_dict: Dict[str, Any] = self.generated_reports[module_fqn]

            # loop through features
            for feature_name in feature_dict:
                # if we need plottable, ensure type of val is tensor
                if plottable:
                    if type(feature_dict[feature_name]) == torch.Tensor:
                        unique_feature_names.add(feature_name)
                else:
                    # any and all features
                    unique_feature_names.add(feature_name)

        # return our compiled set of unique feature names
        return unique_feature_names

    def _get_filtered_data(self, feature_filter: str, module_fqn_filter: str) -> OrderedDict[str, Any]:
        r"""
        Filters the data and returns it in the same ordered dictionary format so the relavent views can be displayed.

        Args:
            feature_filter (str): The feature filter, if we want to filter the set of data to only include
                a certain set of features that include feature_filter
                If feature = "", then we do not filter based on any features
            module_fqn_filter (str): The filter on prefix for the module fqn. All modules that have fqn with
                this prefix will be included
                If module_fqn_filter = "" we do not filter based on module fqn, and include all modules

        First, the data is filtered based on module_fqn, and then filtered based on feature
        Returns an OrderedDict (sorted in order of model) mapping:
            module_fqns -> feature_names -> values
        """
        # create return dict
        filtered_dict: OrderedDict[str, Any] = OrderedDict()

        for module_fqn in self.generated_reports:
            # first filter based on module
            if module_fqn_filter == "" or module_fqn_filter in module_fqn:
                # create entry for module and loop through features
                filtered_dict[module_fqn] = {}
                module_reports = self.generated_reports[module_fqn]
                for feature_name in module_reports:
                    # check if filtering on features and do so if desired
                    if feature_filter == "" or feature_filter in feature_name:
                        filtered_dict[module_fqn][feature_name] = module_reports[feature_name]

        # we have populated the filtered dict, and must return it

        return filtered_dict

    def generate_table_view(self, feature_filter: str = "", module_fqn_filter: str = "") -> Tuple[Dict[str, List[List[Any]]], str]:
        r"""
        Takes in optional filter values and generates two tables with desired information.

        The generated tables are presented in both a list-of-lists format for further manipulation and filtering
        as well as a formatted string that is ready to print

        The reason for the two tables are that they handle different things:
        1.) the first table handles all tensor level information
        2.) the second table handles and displays all channel based information

        The reasoning for this is that having all the info in one table can make it ambiguous which collected
            statistics are global, and which are actually per-channel, so it's better to split it up into two
            tables. This also makes the information much easier to digest given the plethora of statistics collected

        Tensor table columns:
         idx  layer_fqn  feature_1   feature_2   feature_3   .... feature_n
        ----  ---------  ---------   ---------   ---------        ---------

        Per-Channel table columns:

         idx  layer_fqn  channel  feature_1   feature_2   feature_3   .... feature_n
        ----  ---------  -------  ---------   ---------   ---------        ---------

        Args:
            feature_filter (str, optional): Filters the features presented to only those that
                contain this filter substring
                Default = "", results in all the features being printed
            module_fqn_filter (str, optional): Only includes modules with this string
                Default = "", results in all the modules in the reports to be visible in the table

        Returns a tuple with two objects:
            (Dict[strList[List[Any]]]) A dict containing two keys:
            "tensor_level_info", "channel_level_info"
                Each key maps to:
                    A list of lists containing the table information row by row
                    The 0th index row will contain the headers of the columns
                    The rest of the rows will contain data
            (str) The formatted string that contains the tables information to be printed
        Expected Use:
            >>> info, tabluated_str = model_report_visualizer.generate_table_view(*filters)
            >>> print(tabulated_str) # outputs neatly formatted table
        """
        # first get the filtered data
        filtered_data: OrderedDict[str, Any] = self._get_filtered_data(feature_filter, module_fqn_filter)

        # now we split into tensor and per-channel data
        tensor_features: Set[str] = set()
        channel_features: Set[str] = set()

        # keep track of the number of channels we have
        num_channels: int = 0

        for module_fqn in filtered_data:
            for feature_name in filtered_data[module_fqn]:
                # get the data for that specific feature
                feature_data = filtered_data[module_fqn][feature_name]

                # if it is only a single value, is tensor, otherwise per channel
                try:
                    iterator = iter(feature_data)
                except TypeError:
                    # means is per-tensor
                    tensor_features.add(feature_name)
                else:
                    # works means per channel
                    channel_features.add(feature_name)
                    num_channels = len(feature_data)

        # we make them lists for iteration purposes
        tensor_features_list: List[str] = sorted(list(tensor_features))
        channel_features_list: List[str] = sorted(list(channel_features))

        # now we compose the tensor information table
        tensor_table: List[List[Any]] = []

        # first add a row of headers to the table
        tensor_headers: List[str] = ["idx", "layer_fqn"] + tensor_features_list
        tensor_table.append(tensor_headers)

        # now we add all the data
        for index, module_fqn in enumerate(filtered_data):
            # we make a new row for the tensor table
            tensor_table_row = [index + 1, module_fqn]
            for feature in tensor_features_list:
                # we iterate in same order of added features

                if feature in filtered_data[module_fqn]:
                    # add value if applicable to module
                    feature_val = filtered_data[module_fqn][feature]
                else:
                    # add that it is not applicable
                    feature_val = "Not Applicable"

                # if it's a tensor we want to extract val
                if type(feature_val) is torch.Tensor:
                    feature_val = feature_val.item()

                # we add to our list of values
                tensor_table_row.append(feature_val)

            # append the table row to the table
            tensor_table.append(tensor_table_row)

        # now we compose the table for the channel information table
        channel_table: List[List[Any]] = []

        # first add a row of headers to the table
        channel_headers: List[str] = ["idx", "layer_fqn", "channel"] + channel_features_list
        channel_table.append(channel_headers)

        # counter to keep track of number of entries in
        channel_table_entry_counter: int = 1

        # now we add all channel data
        for index, module_fqn in enumerate(filtered_data):
            # we iterate over all channels
            for channel in range(num_channels):
                # we make a new row for the channel
                new_channel_row = [channel_table_entry_counter, module_fqn, channel]
                for feature in channel_features_list:
                    if feature in filtered_data[module_fqn]:
                        # add value if applicable to module
                        feature_val = filtered_data[module_fqn][feature][channel]
                    else:
                        # add that it is not applicable
                        feature_val = "Not Applicable"

                    # if it's a tensor we want to extract val
                    if type(feature_val) is torch.Tensor:
                        feature_val = feature_val.item()

                    # add value to channel specific row
                    new_channel_row.append(feature_val)

                # add to table and increment row index counter
                channel_table.append(new_channel_row)
                channel_table_entry_counter += 1

        # now we have populated the tables for each one
        # let's create the strings to be returned
        table_str = ""
        if len(tensor_features_list) > 0:
            table_str += "Tensor Level Information \n"
            table_str += tabulate(tensor_table, headers="firstrow")
        if len(channel_features_list) > 0:
            table_str += "\n\n Channel Level Information \n"
            table_str += tabulate(channel_table, headers="firstrow")

        # if no features at all, let user know
        if table_str == "":
            table_str = "No data points to generate table with."

        # let's now create the dictionary to return
        table_dict = {
            self.TABLE_TENSOR_KEY : tensor_table,
            self.TABLE_CHANNEL_KEY : channel_table
        }

        return (table_dict, table_str)


    def generate_plot_view(self, feature: str, module_fqn_prefix_filter: str = "") -> List[List[Any]]:
        r"""
        Takes in a feature and optional module_filter and generates a line plot of the desired data.

        Note:
            Only features in the report that have tensor value data are plottable by this class

        Args:
            feature (str): The specific feature we wish to generate the plot for
            module_fqn_prefix_filter (str, optional): Only includes modules with this string prefix
                Default = "", results in all the modules in the reports to be visible in the plot

        Returns a tuple with two objects:
            (List[List[Any]]) A list of lists containing the plot information row by row
                The 0th index row will contain the headers of the columns
                The rest of the rows will contain data
        Expected Use:
            >>> # the code below both returns the info and diplays the plot
            >>> info = model_report_visualizer.generate_plot_view(*filters)
        """
        pass

    def generate_histogram_view(self, feature: str, module_fqn_prefix_filter: str = "") -> List[List[Any]]:
        r"""
        Takes in a feature and optional module_filter and generates a histogram of the desired data.

        Note:
            Only features in the report that have tensor value data can be viewed as a histogram

        Args:
            feature (str): The specific feature we wish to generate the plot for
            module_fqn_prefix_filter (str, optional): Only includes modules with this string prefix
                Default = "", results in all the modules in the reports to be visible in the histogram

        Returns a tuple with two objects:
            (List[List[Any]]) A list of lists containing the histogram information row by row
                The 0th index row will contain the headers of the columns
                The rest of the rows will contain data
        Expected Use:
            >>> # the code below both returns the info and displays the histogram
            >>> info = model_report_visualizer.generate_histogram_view(*filters)
        """
        pass