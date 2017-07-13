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

from dolfin import FunctionSpace
from rbnics.backends.basic.wrapping import functions_list_basis_functions_matrix_adapter
from rbnics.backends.dolfin.wrapping.function_copy import function_copy
from rbnics.backends.online import OnlineFunction, OnlineMatrix, OnlineVector

def functions_list_basis_functions_matrix_mul_online_matrix(functions_list_basis_functions_matrix, online_matrix, FunctionsListBasisFunctionsMatrixType, backend):
    V = functions_list_basis_functions_matrix.V_or_Z
    (functions, _) = functions_list_basis_functions_matrix_adapter(functions_list_basis_functions_matrix, backend)
    assert isinstance(V, FunctionSpace)
    assert isinstance(online_matrix, OnlineMatrix.Type())
    
    output = FunctionsListBasisFunctionsMatrixType(V)
    dim = online_matrix.shape[1]
    for j in range(dim):
        assert len(online_matrix[:, j]) == len(functions)
        output_j = function_copy(functions[0])
        output_j.vector().zero()
        for (i, fun_i) in enumerate(functions):
            online_matrix_ij = float(online_matrix[i, j])
            output_j.vector().add_local(fun_i.vector().array()*online_matrix_ij)
        output_j.vector().apply("add")
        output.enrich(output_j)
    return output

def functions_list_basis_functions_matrix_mul_online_vector(functions_list_basis_functions_matrix, online_vector, backend):
    (functions, _) = functions_list_basis_functions_matrix_adapter(functions_list_basis_functions_matrix, backend)
    assert isinstance(online_vector, (OnlineVector.Type(), tuple))
    
    output = function_copy(functions[0])
    output.vector().zero()
    for (i, fun_i) in enumerate(functions):
        online_vector_i = float(online_vector[i])
        output.vector().add_local(fun_i.vector().array()*online_vector_i)        
    output.vector().apply("add")
    return output
    
def functions_list_basis_functions_matrix_mul_online_function(functions_list_basis_functions_matrix, online_function, backend):
    assert isinstance(online_function, OnlineFunction.Type())
    
    return functions_list_basis_functions_matrix_mul_online_vector(functions_list_basis_functions_matrix, online_function.vector(), backend)
    
