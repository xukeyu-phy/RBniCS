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

from rbnics.backends.fenics.wrapping.tensor_copy import tensor_copy
import rbnics.backends # avoid circular imports when importing fenics and numpy backends

def tensors_list_mul_online_function(tensors_list, online_function):
    assert isinstance(online_function, rbnics.backends.numpy.Function.Type())
    online_vector = online_function.vector()
    
    output = tensor_copy(tensors_list._list[0])
    output.zero()
    assert isinstance(output, (rbnics.backends.fenics.Matrix.Type(), rbnics.backends.fenics.Vector.Type()))
    if isinstance(output, rbnics.backends.fenics.Matrix.Type()):
        for (i, matrix_i) in enumerate(tensors_list._list):
            output += matrix_i*online_vector.item(i)
    elif isinstance(output, rbnics.backends.fenics.Vector.Type()):
        for (i, vector_i) in enumerate(tensors_list._list):
            output.add_local(vector_i.array()*online_vector.item(i))
        output.apply("add")
    else: # impossible to arrive here anyway, thanks to the assert
        raise AssertionError("Invalid arguments in tensors_list_mul_online_function.")
    return output
    
