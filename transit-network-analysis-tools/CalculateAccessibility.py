################################################################################
## Toolbox: Transit Network Analysis Tools
## Tool name: Calculate Accessibility Matrix
## Created by: Melinda Morang, Esri
## Last updated: 17 June 2019
################################################################################
'''Count the number of destinations reachable from each origin by transit and 
walking. The tool calculates an Origin-Destination Cost Matrix for each start 
time within a time window because the reachable destinations change depending 
on the time of day because of the transit schedules.  The output gives the 
total number of destinations reachable at least once as well as the number of 
destinations reachable at least 10%, 20%, ...90% of start times during the time 
window.  The number of reachable destinations can be weighted based on a field, 
such as the number of jobs available at each destination.  The tool also 
calculates the percentage of total destinations reachable.'''
################################################################################
'''Copyright 2019 Esri
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.'''
################################################################################

import arcpy
import AnalysisHelpers
arcpy.env.overwriteOutput = True

class CustomError(Exception):
    pass


def runTool(input_network_analyst_layer, origins_feature_class, destinations_feature_class,
            destinations_weight_field=None, start_day_input="Wednesday", start_time_input="08:00",
            end_day_input="Wednesday", end_time_input="09:00", increment_input=1):
    """Solves an Origin-Destination Cost Matrix analysis for multiple times of day and summarizes the results.
    
    The user specifies a time window, and the tool will run the analysis for each minute within the time window. In
    addition to counting the total number of destinations reachable at least once during the time window, the tool
    output also shows the number of destinations reachable at least 10%, 20%, ...90% of start times during the time
    window.

    Parameters: 
    input_network_analyst_layer: An OD Cost Matrix layer in your map or saved as a layer file.
    origins_feature_class: A point feature class representing the locations you want to calculate accessibility measures
        for. For example, your origins might be census block centroids or the centroids of individual parcels.
    destinations_feature_class: A point feature class representing the destinations your origins will travel to. For
        example, if you want to measure your origins' level of accessibility to jobs, your Destinations could be the
        locations of employment centers.
    destinations_weight_field: Optionally, choose a field from your destinations_feature_class that will be used as a
        weight. For example, if your destinations represent employment centers, the weight field could be the number of
        jobs available at each point. Only integer and double fields can be used for the weight field. If you do not
        choose a weight field, each destination will be counted as 1.
    start_day_input: Day of the week or YYYYMMDD date for the first start time of your analysis.
    start_time_input: The lower end of the time window you wish to analyze. Must be in HH:MM format (24-hour time). For
        example, 2 AM is 02:00, and 2 PM is 14:00.
    end_day_input:  If you're using a generic weekday for start_day_input, you must use the same day. If you want to run
        an analysis spanning multiple days, choose specific YYYYMMDD dates for both start_day_input and end_day_input.
    end_time_input: The upper end of the time window you wish to analyze. Must be in HH:MM format (24-hour time). The
        end_time_input is inclusive, meaning that an analysis will be performed for the time of day you enter here.
    increment_input: Increment the OD Cost Matrix's time of day by this amount between solves. For example, for a
        increment_input of 1 minute, the OD Cost Matrix will be solved for 10:00, 10:01, 10:02, etc. A increment_input
        of 2 minutes would calculate the OD Cost Matrix for 10:00, 10:02, 10:04, etc.

    """

    try:

        #Check out the Network Analyst extension license
        if arcpy.CheckExtension("Network") == "Available":
            arcpy.CheckOutExtension("Network")
        else:
            arcpy.AddError("You must have a Network Analyst license to use this tool.")
            raise CustomError


        # ----- Get and process inputs -----

        # OD layer from the map or .lyr file that with all the desired settings
        # (except time of day - we'll adjust that in this script)
        # Does not need Origins and Destinations loaded. We'll do that in the script.
        desc = arcpy.Describe(input_network_analyst_layer)
        if desc.dataType != "NALayer" or desc.solverName != "OD Cost Matrix Solver":
            arcpy.AddError("Input layer must be an OD Cost Matrix layer.")
            raise CustomError

        # Make sure origins and destinations aren't empty
        empty_error = u"Your %s feature class is empty.  Please choose a feature class containing points you wish to analyze."
        if int(arcpy.management.GetCount(origins_feature_class).getOutput(0)) == 0:
            arcpy.AddError(empty_error % "Origins")
            raise CustomError
        if int(arcpy.management.GetCount(destinations_feature_class).getOutput(0)) == 0:
            arcpy.AddError(empty_error % "Destinations")
            raise CustomError

        # Make list of times of day to run the analysis
        try:
            timelist = AnalysisHelpers.make_analysis_time_of_day_list(start_day_input, end_day_input, start_time_input, end_time_input, increment_input)
        except:
            raise CustomError

        # If the input NA layer is a layer file, convert it to a layer object
        if not AnalysisHelpers.isPy3:
            if isinstance(input_network_analyst_layer, (unicode, str)) and input_network_analyst_layer.endswith(".lyr"):
                input_network_analyst_layer = arcpy.mapping.Layer(input_network_analyst_layer)
        else:
            if isinstance(input_network_analyst_layer, str) and input_network_analyst_layer.endswith(".lyrx"):
                input_network_analyst_layer = arcpy.mp.LayerFile(input_network_analyst_layer).listLayers()[0]

        
        # ----- Add Origins and Destinations to the OD layer -----

        arcpy.AddMessage("Adding Origins and Destinations to OD Cost Matrix Layer...")

        # Get Origins and Destionations Describe objects for later use
        origins_desc = arcpy.Describe(origins_feature_class)
        destinations_desc = arcpy.Describe(destinations_feature_class)

        # Get the sublayer names and objects for use later
        sublayer_names = arcpy.na.GetNAClassNames(input_network_analyst_layer) # To ensure compatibility with localized software
        origins_sublayer_name = sublayer_names["Origins"]
        destinations_sublayer_name = sublayer_names["Destinations"]
        lines_sublayer_name = sublayer_names["ODLines"]
        if not AnalysisHelpers.isPy3:
            origins_subLayer = arcpy.mapping.ListLayers(input_network_analyst_layer, origins_sublayer_name)[0]
            destinations_subLayer = arcpy.mapping.ListLayers(input_network_analyst_layer, destinations_sublayer_name)[0]
            lines_subLayer = arcpy.mapping.ListLayers(input_network_analyst_layer, lines_sublayer_name)[0]
        else:
            origins_subLayer = input_network_analyst_layer.listLayers(origins_sublayer_name)[0]
            destinations_subLayer = input_network_analyst_layer.listLayers(destinations_sublayer_name)[0]
            lines_subLayer = input_network_analyst_layer.listLayers(lines_sublayer_name)[0]

        # Keep track of the ObjectID field of the input
        origins_objectID = origins_desc.OIDFieldName
        destinations_objectID = destinations_desc.OIDFieldName
        arcpy.na.AddFieldToAnalysisLayer(input_network_analyst_layer, origins_sublayer_name, "InputOID", "LONG")
        fieldMappings_origins = arcpy.na.NAClassFieldMappings(input_network_analyst_layer, origins_sublayer_name)
        fieldMappings_origins["InputOID"].mappedFieldName = origins_objectID
        arcpy.na.AddFieldToAnalysisLayer(input_network_analyst_layer, destinations_sublayer_name, "InputOID", "LONG")
        fieldMappings_destinations = arcpy.na.NAClassFieldMappings(input_network_analyst_layer, destinations_sublayer_name)
        fieldMappings_destinations["InputOID"].mappedFieldName = destinations_objectID

        # If using a weight field, filter out destinations with 0 or Null weight since they will not contribute to the final output
        destinations_layer = destinations_feature_class
        if destinations_weight_field:
            expression = u"%s IS NOT NULL AND %s <> 0" % (destinations_weight_field, destinations_weight_field)
            destinations_layer = arcpy.management.MakeFeatureLayer(destinations_feature_class, "Dests", expression)
            if int(arcpy.management.GetCount(destinations_layer).getOutput(0)) == 0:
                arcpy.AddError(u"The weight field %s of your input Destinations table has values of 0 or Null for all rows." % destinations_weight_field)
                raise CustomError

        # Add origins and destinations
        arcpy.na.AddLocations(input_network_analyst_layer, origins_sublayer_name, origins_feature_class, fieldMappings_origins, "", append="CLEAR")
        arcpy.na.AddLocations(input_network_analyst_layer, destinations_sublayer_name, destinations_layer, fieldMappings_destinations, "", append="CLEAR")

        # Create dictionary linking the ObjectID fields of the input feature classes and the NA sublayers
        # We need to do this because, particularly when the NA layer already had data in it, the ObjectID
        # values don't always start with 1.
        origins_oid_dict = {} # {Input feature class Object ID: Origins sublayer OID}
        origin_ids = []
        with arcpy.da.SearchCursor(origins_subLayer, ["OID@", "InputOID"]) as cur:
            for row in cur:
                origin_ids.append(row[0])
                origins_oid_dict[row[1]] = row[0]
        destinations_oid_dict = {} # {Destination sublayer OID, Input feature class Object ID: }
        with arcpy.da.SearchCursor(destinations_subLayer, ["OID@", "InputOID"]) as cur:
            for row in cur:
                destinations_oid_dict[row[0]] = row[1]


        # ----- Solve NA layer in a loop for each time of day -----

        # Initialize a dictionary for counting the number of times each destination is reached by each origin
        OD_count_dict = {} # {Origin OID: {Destination OID: Number of times reached}}

        # Grab the solver properties object from the NA layer so we can set the time of day
        solverProps = arcpy.na.GetSolverProperties(input_network_analyst_layer)

        # Solve for each time of day and save output
        arcpy.AddMessage("Solving OD Cost matrix at time...")
        for t in timelist:
            arcpy.AddMessage(str(t))
            
            # Switch the time of day
            solverProps.timeOfDay = t
            
            # Solve the OD Cost Matrix
            try:
                arcpy.na.Solve(input_network_analyst_layer)
            except:
                # Solve failed.  It could be that no destinations were reachable within the time limit,
                # or it could be another error.  Running out of memory is a distinct possibility.
                errs = arcpy.GetMessages(2)
                if "No solution found" not in errs:
                    # Only alert them if it's some weird error.
                    arcpy.AddMessage("Solve failed.  Errors: %s. Continuing to next time of day." % errs)
                continue

            # Read the OD matrix output and increment the dictionary
            # There is one entry in Lines for each OD pair that was reached within the cutoff time
            with arcpy.da.SearchCursor(lines_subLayer, ["OriginID", "DestinationID"]) as cur:
                for line in cur:
                    if line[0] not in OD_count_dict:
                        OD_count_dict[line[0]] = {}
                    if line[1] not in OD_count_dict[line[0]]:
                        OD_count_dict[line[0]][line[1]] = 1
                    else:
                        OD_count_dict[line[0]][line[1]] += 1


        # ----- Calculate statistics and generate output -----

        arcpy.AddMessage("Calculating statistics and writing results...")

        # If the destinations are weighted (eg, number of jobs at each destination), track them here
        destination_weight_dict = {} # {Input Destinations feature class ObjectID: Weight}
        num_dests = 0
        if destinations_weight_field:
            with arcpy.da.SearchCursor(destinations_layer, ["OID@", destinations_weight_field]) as cur:
                for row in cur:
                    destination_weight_dict[row[0]] = row[1]
                    num_dests += row[1]
        else:
            num_dests = len(destinations_oid_dict)

        # Add fields to input origins for output statistics. If the fields already exist, this will do nothing.
        arcpy.management.AddField(origins_feature_class, "TotalDests", "LONG")
        arcpy.management.AddField(origins_feature_class, "PercDests", "DOUBLE")
        stats_fields = ["TotalDests", "PercDests"]
        for i in range(1, 10):
            dest_field = "DsAL%i0Perc" % i
            perc_field = "PsAL%i0Perc" % i
            stats_fields.append(dest_field)
            stats_fields.append(perc_field)
            arcpy.management.AddField(origins_feature_class, dest_field, "LONG")
            arcpy.management.AddField(origins_feature_class, perc_field, "DOUBLE")
        
        # For each origin, calculate statistics
        with arcpy.da.UpdateCursor(origins_feature_class, ["OID@"] + stats_fields) as cur:
            for row in cur:
                origin_OID = origins_oid_dict[row[0]]
                reachable_dests = 0
                # Dictionary to track not just whether a destination was ever reachable, but how frequently it was reachable
                # Keys are percentage of times reachable, 10% of times, 20% of times, etc.
                reachable_dests_perc = {i:0 for i in range(10, 100, 10)}
                # Loop through all destinations
                if origin_OID in OD_count_dict: # If it's not present, that means no destinations were ever found for this origin
                    for dest in OD_count_dict[origin_OID]:
                        if OD_count_dict[origin_OID][dest] > 0: # If this destination was ever reachable by this origin
                            # Calculate the percentage of start times when this destination was reachable
                            percent_of_times_reachable = (float(OD_count_dict[origin_OID][dest]) / float(len(timelist))) * 100
                            if destination_weight_dict:
                                # If using a weight field, determine how much weight reaching this destination contributes to the total
                                dests_to_add = destination_weight_dict[destinations_oid_dict[dest]]
                            else:
                                # Otherwise, just count it as 1
                                dests_to_add = 1
                            # Increment the total number of destinations that were ever reached by this origin
                            reachable_dests += dests_to_add
                            # Also increment the percentage counters
                            for perc in reachable_dests_perc:
                                # If the actual percent of times reached is greater than the counter threshold, increment the counter
                                if percent_of_times_reachable >= perc:
                                    reachable_dests_perc[perc] += dests_to_add
                # Calculate the percentage of all destinations that were ever reached
                percent_dests = (float(reachable_dests) / float(num_dests)) * 100
                row[1] = reachable_dests
                row[2] = percent_dests
                # Populate the percent of times fields
                for r in range(0, 9):
                    row[3 + 2*r] = reachable_dests_perc[10 + 10*r]
                    # Calculate the percentage of all destinations that were reached at least this percent of times
                    row[3 + 2*r + 1] = (float(reachable_dests_perc[10 + 10*r]) / float(num_dests)) * 100
                cur.updateRow(row)

        arcpy.AddMessage("Done!  Statistics fields have been added to your input Origins layer.")

    except CustomError:
        pass
    except:
        raise
