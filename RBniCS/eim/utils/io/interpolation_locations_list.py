# Copyright (C) 2015-2016 by the RBniCS authors
#
# This file is part of RBniCS.
#
# RBniCS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RBniCS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with RBniCS. If not, see <http://www.gnu.org/licenses/>.
#
## @file functions_list.py
#  @brief Type for storing a list of FE functions.
#
#  @author Francesco Ballarin <francesco.ballarin@sissa.it>
#  @author Gianluigi Rozza    <gianluigi.rozza@sissa.it>
#  @author Alberto   Sartori  <alberto.sartori@sissa.it>

###########################     OFFLINE STAGE     ########################### 
## @defgroup OfflineStage Methods related to the offline stage
#  @{

from RBniCS.utils.io import ExportableList
from RBniCS.utils.decorators import Extends, override

@Extends(ExportableList)
class InterpolationLocationsList(ExportableList):
    @override
    def __init__(self, expression):
        ExportableList.__init__(self, "pickle")
        self.expression = expression
        # Auxiliary list to store processor_id
        self.processors_id = list()
        
    @override
    def load(self, directory, filename):
        return_value = ExportableList.load(self, directory, filename)
        # Make sure to update the processor ids
        N = len(self)
        for i in range(N):
            location = ExportableList.__getitem__(self, i)
            self.processors_id.append(self.expression.get_processor_id(location))
        return return_value
        
    @override
    def append(self, location):
        ExportableList.append(self, location)
        # Make sure to update the processor ids
        self.processors_id.append(self.expression.get_processor_id(location))
        
    @override
    def __getitem__(self, key):
        location = ExportableList.__getitem__(self, key)
        processor_id = self.processors_id[key]
        return (location, processor_id)
        
#  @}
########################### end - OFFLINE STAGE - end ########################### 

