# Copyright (C) 2015-2017 by the RBniCS authors
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

# Import the minimum subset of RBniCS required to run tutorials
from rbnics.eim.problems import DEIM, EIM, ExactParametrizedFunctions

__all__ = [
    # rbnics.eim.problems
    'DEIM',
    'EIM',
    'ExactParametrizedFunctions'
]

# Import also reduced problems and reduction methods to make sure that 
# decorators that fill in algorithm factories are called, but do not 
# add them to __all__ since they are not class that should be explicitely
# used in the tutorials
from rbnics.eim.problems import DEIMDecoratedReducedProblem, EIMDecoratedReducedProblem, ExactParametrizedFunctionsDecoratedReducedProblem
from rbnics.eim.reduction_methods import DEIMDecoratedReductionMethod, EIMDecoratedReductionMethod, ExactParametrizedFunctionsDecoratedReductionMethod

