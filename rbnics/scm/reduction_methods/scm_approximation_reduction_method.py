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

from __future__ import print_function
from numpy import isclose
from rbnics.backends import transpose
from rbnics.backends.online import OnlineVector
from rbnics.reduction_methods.base import ReductionMethod
from rbnics.utils.io import ErrorAnalysisTable, Folders, GreedySelectedParametersList, GreedyErrorEstimatorsList, SpeedupAnalysisTable, Timer
from rbnics.utils.mpi import print
from rbnics.utils.decorators import Extends, override
from rbnics.scm.problems import ParametrizedCoercivityConstantEigenProblem

# Empirical interpolation method for the interpolation of parametrized functions
@Extends(ReductionMethod)
class SCMApproximationReductionMethod(ReductionMethod):
    
    ## Default initialization of members
    @override
    def __init__(self, SCM_approximation, folder_prefix):
        # Call the parent initialization
        ReductionMethod.__init__(self, folder_prefix, SCM_approximation.mu_range)
        
        # $$ OFFLINE DATA STRUCTURES $$ #
        # High fidelity problem
        self.SCM_approximation = SCM_approximation
        # I/O
        self.folder["snapshots"] = self.folder_prefix + "/" + "snapshots"
        self.folder["post_processing"] = self.folder_prefix + "/" + "post_processing"
        self.greedy_selected_parameters = GreedySelectedParametersList()
        self.greedy_error_estimators = GreedyErrorEstimatorsList()
        #
        self._offline__mu_index = 0
        
        # Get data that were temporarily store in the SCM_approximation
        self.bounding_box_minimum_eigensolver_parameters = self.SCM_approximation._input_storage_for_SCM_reduction["bounding_box_minimum_eigensolver_parameters"]
        self.bounding_box_maximum_eigensolver_parameters = self.SCM_approximation._input_storage_for_SCM_reduction["bounding_box_maximum_eigensolver_parameters"]
        del self.SCM_approximation._input_storage_for_SCM_reduction

    ## OFFLINE: set the elements in the training set.
    @override
    def initialize_training_set(self, ntrain, enable_import=True, sampling=None, **kwargs):
        assert enable_import
        import_successful = ReductionMethod.initialize_training_set(self, ntrain, enable_import, sampling)
        self.SCM_approximation.training_set = self.training_set
        return import_successful
    
    ## Initialize data structures required for the offline phase
    @override
    def _init_offline(self):
        # Prepare folders and init SCM approximation
        all_folders = Folders()
        all_folders.update(self.folder)
        all_folders.update(self.SCM_approximation.folder)
        all_folders.pop("testing_set") # this is required only in the error analysis
        at_least_one_folder_created = all_folders.create()
        if not at_least_one_folder_created:
            self.SCM_approximation.init("online")
            return False # offline construction should be skipped, since data are already available
        else:
            self.SCM_approximation.init("offline")
            return True # offline construction should be carried out
            
    ## Finalize data structures required after the offline phase
    @override
    def _finalize_offline(self):
        self.SCM_approximation.init("online")
    
    ## Perform the offline phase of SCM
    @override
    def offline(self):
        need_to_do_offline_stage = self._init_offline()
        if not need_to_do_offline_stage:
            return self.SCM_approximation
        
        print("==============================================================")
        print("=" + "{:^60}".format("SCM offline phase begins") + "=")
        print("==============================================================")
        print("")
        
        # Compute the bounding box \mathcal{B}
        self.compute_bounding_box()
        print("")
        
        # Arbitrarily start from the first parameter in the training set
        self.SCM_approximation.set_mu(self.training_set[0])
        self._offline__mu_index = 0
        relative_error_estimator_max = 2.*self.tol
        
        while self.SCM_approximation.N < self.Nmax and relative_error_estimator_max >= self.tol:
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ SCM N =", self.SCM_approximation.N, "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            
            # Store the greedy parameter
            self.update_C_J()
            
            # Evaluate the coercivity constant
            print("evaluate the stability factor for mu =", self.SCM_approximation.mu)
            (alpha, eigenvector) = self.SCM_approximation.exact_coercivity_constant_calculator.solve()
            print("stability factor =", alpha)
            
            # Update internal data structures
            self.update_alpha_J(alpha)
            self.update_eigenvector_J(eigenvector)
            UB_vector = self.compute_UB_vector(eigenvector)
            self.update_UB_vectors_J(UB_vector)
            
            # Prepare for next iteration
            print("find next mu")
            (error_estimator_max, relative_error_estimator_max) = self.greedy()
            print("maximum SCM error estimator =", error_estimator_max)
            print("maximum SCM relative error estimator =", relative_error_estimator_max)
            
            print("")
        
        print("==============================================================")
        print("=" + "{:^60}".format("SCM offline phase ends") + "=")
        print("==============================================================")
        print("")
        
        # mu_index does not make any sense from now on
        self._offline__mu_index = None
        
        self._finalize_offline()
        return self.SCM_approximation
        
    # Compute the bounding box \mathcal{B}
    def compute_bounding_box(self):
        # Resize the bounding box storage
        Q = self.SCM_approximation.truth_problem.Q["a"]
        
        for q in range(Q):
            # Compute the minimum eigenvalue
            minimum_eigenvalue_calculator = ParametrizedCoercivityConstantEigenProblem(self.SCM_approximation.truth_problem, ("a", q), False, "smallest", self.bounding_box_minimum_eigensolver_parameters)
            minimum_eigenvalue_calculator.init()
            (self.SCM_approximation.B_min[q], _) = minimum_eigenvalue_calculator.solve()
            print("B_min[" + str(q) + "] = " + str(self.SCM_approximation.B_min[q]))
            
            # Compute the maximum eigenvalue
            maximum_eigenvalue_calculator = ParametrizedCoercivityConstantEigenProblem(self.SCM_approximation.truth_problem, ("a", q), False, "largest", self.bounding_box_maximum_eigensolver_parameters)
            maximum_eigenvalue_calculator.init()
            (self.SCM_approximation.B_max[q], _) = maximum_eigenvalue_calculator.solve()
            print("B_max[" + str(q) + "] = " + str(self.SCM_approximation.B_max[q]))
        
        # Save to file
        self.SCM_approximation.B_min.save(self.SCM_approximation.folder["reduced_operators"], "B_min")
        self.SCM_approximation.B_max.save(self.SCM_approximation.folder["reduced_operators"], "B_max")
        
    # Store the greedy parameter
    def update_C_J(self):
        mu = self.SCM_approximation.mu
        mu_index = self._offline__mu_index
        assert mu == self.training_set[mu_index]
        
        self.SCM_approximation.C_J.append(mu_index)
        self.SCM_approximation.N = len(self.SCM_approximation.C_J)
        
        if mu_index in self.SCM_approximation.complement_C_J: # if not SCM selects twice the same parameter
            self.SCM_approximation.complement_C_J.remove(mu_index)
        
        # Save to file
        self.SCM_approximation.C_J.save(self.SCM_approximation.folder["reduced_operators"], "C_J")
        self.SCM_approximation.complement_C_J.save(self.SCM_approximation.folder["reduced_operators"], "complement_C_J")
        
    def update_alpha_J(self, alpha):
        self.SCM_approximation.alpha_J.append(alpha)
        self.SCM_approximation.alpha_J.save(self.SCM_approximation.folder["reduced_operators"], "alpha_J")
        
    def update_eigenvector_J(self, eigenvector):
        self.SCM_approximation.eigenvector_J.append(eigenvector)
        self.SCM_approximation.export_solution(self.folder["snapshots"], "eigenvector_" + str(len(self.SCM_approximation.eigenvector_J) - 1), eigenvector)
        
    ## Compute the ratio between a_q(u,u) and s(u,u), for all q in vec
    def compute_UB_vector(self, u):
        Q = self.SCM_approximation.truth_problem.Q["a"]
        X = self.SCM_approximation.truth_problem.inner_product[0]
        UB_vector = OnlineVector(Q)
        norm_S_squared = transpose(u)*X*u
        for q in range(Q):
            A_q = self.SCM_approximation.truth_problem.operator["a"][q]
            UB_vector[q] = (transpose(u)*A_q*u)/norm_S_squared
        return UB_vector
        
    def update_UB_vectors_J(self, UB_vector):
        self.SCM_approximation.UB_vectors_J.append(UB_vector)
        self.SCM_approximation.UB_vectors_J.save(self.SCM_approximation.folder["reduced_operators"], "UB_vectors_J")
        
    ## Choose the next parameter in the offline stage in a greedy fashion
    def greedy(self):
        def solve_and_estimate_error(mu, index):
            self._offline__mu_index = index
            self.SCM_approximation.set_mu(mu)
            
            LB = self.SCM_approximation.get_stability_factor_lower_bound(mu, False)
            UB = self.SCM_approximation.get_stability_factor_upper_bound(mu)
            error_estimator = (UB - LB)/UB
            
            if LB/UB < 0 and not isclose(LB/UB, 0.): # if LB/UB << 0
                print("SCM warning at mu =", mu , ": LB =", LB, "< 0")
            if LB/UB > 1 and not isclose(LB/UB, 1.): # if LB/UB >> 1
                print("SCM warning at mu =", mu , ": LB =", LB, "> UB =", UB)
                
            self.SCM_approximation.alpha_LB_on_training_set[index] = max(0, LB)
            return error_estimator
            
        (error_estimator_max, error_estimator_argmax) = self.training_set.max(solve_and_estimate_error)
        self.SCM_approximation.set_mu(self.training_set[error_estimator_argmax])
        self._offline__mu_index = error_estimator_argmax
        self.greedy_selected_parameters.append(self.training_set[error_estimator_argmax])
        self.greedy_selected_parameters.save(self.folder["post_processing"], "mu_greedy")
        self.greedy_error_estimators.append(error_estimator_max)
        self.greedy_error_estimators.save(self.folder["post_processing"], "error_estimator_max")
        self.SCM_approximation.alpha_LB_on_training_set.save(self.SCM_approximation.folder["reduced_operators"], "alpha_LB_on_training_set")
        return (error_estimator_max, error_estimator_max/self.greedy_error_estimators[0])
        
    ## Initialize data structures required for the error analysis phase
    @override
    def _init_error_analysis(self, **kwargs):
        # Initialize the exact coercivity constant object
        self.SCM_approximation.exact_coercivity_constant_calculator.init()
        
        # Initialize reduced order data structures in the SCM online problem
        self.SCM_approximation.init("online")
    
    # Compute the error of the scm approximation with respect to the
    # exact coercivity over the testing set
    @override
    def error_analysis(self, N=None, **kwargs):
        if N is None:
            N = self.SCM_approximation.N
        assert len(kwargs) == 0 # not used in this method
            
        self._init_error_analysis(**kwargs)
        
        print("==============================================================")
        print("=" + "{:^60}".format("SCM error analysis begins") + "=")
        print("==============================================================")
        print("")
        
        error_analysis_table = ErrorAnalysisTable(self.testing_set)
        error_analysis_table.set_Nmin(N)
        error_analysis_table.set_Nmax(N)
        error_analysis_table.add_column("normalized_error", group_name="scm", operations=("min", "mean", "max"))
        
        for (run, mu) in enumerate(self.testing_set):
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ SCM run =", run, "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            
            self.SCM_approximation.set_mu(mu)
            
            (exact, _) = self.SCM_approximation.exact_coercivity_constant_calculator.solve()
            LB = self.SCM_approximation.get_stability_factor_lower_bound(self.SCM_approximation.mu, False)
            UB = self.SCM_approximation.get_stability_factor_upper_bound(self.SCM_approximation.mu)
            
            from numpy import isclose
            if LB/UB < 0 and not isclose(LB/UB, 0.): # if LB/UB << 0
                print("SCM warning at mu =", self.SCM_approximation.mu , ": LB =", LB, "< 0")
            if LB/UB > 1 and not isclose(LB/UB, 1.): # if LB/UB >> 1
                print("SCM warning at mu =", self.SCM_approximation.mu , ": LB =", LB, "> UB =", UB)
            if LB/exact > 1 and not isclose(LB/exact, 1.): # if LB/exact >> 1
                print("SCM warning at mu =", self.SCM_approximation.mu , ": LB =", LB, "> exact =", exact)
            
            error_analysis_table["normalized_error", N, run] = (exact - LB)/UB
        
        # Print
        print("")
        print(error_analysis_table)
        
        print("")
        print("==============================================================")
        print("=" + "{:^60}".format("SCM error analysis ends") + "=")
        print("==============================================================")
        print("")
        
        self._finalize_error_analysis(**kwargs)
        
    # Compute the speedup of the scm approximation with respect to the
    # exact coercivity over the testing set
    @override
    def speedup_analysis(self, N=None, **kwargs):
        if N is None:
            N = self.SCM_approximation.N
        assert len(kwargs) == 0 # not used in this method
            
        self._init_speedup_analysis(**kwargs)
        
        print("==============================================================")
        print("=" + "{:^60}".format("SCM speedup analysis begins") + "=")
        print("==============================================================")
        print("")
        
        speedup_analysis_table = SpeedupAnalysisTable(self.testing_set)
        speedup_analysis_table.set_Nmin(N)
        speedup_analysis_table.set_Nmax(N)
        speedup_analysis_table.add_column("speedup", group_name="speedup", operations=("min", "mean", "max"))
        
        exact_timer = Timer("parallel")
        SCM_timer = Timer("serial")
        
        for (run, mu) in enumerate(self.testing_set):
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ SCM run =", run, "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            
            self.SCM_approximation.set_mu(mu)
            
            exact_timer.start()
            self.SCM_approximation.exact_coercivity_constant_calculator.solve()
            elapsed_exact = exact_timer.stop()
            
            SCM_timer.start()
            LB = self.SCM_approximation.get_stability_factor_lower_bound(self.SCM_approximation.mu, False)
            UB = self.SCM_approximation.get_stability_factor_upper_bound(self.SCM_approximation.mu)
            elapsed_SCM = SCM_timer.stop()
            
            speedup_analysis_table["speedup", N, run] = elapsed_exact/elapsed_SCM
        
        # Print
        print("")
        print(speedup_analysis_table)
        
        print("")
        print("==============================================================")
        print("=" + "{:^60}".format("SCM speedup analysis ends") + "=")
        print("==============================================================")
        print("")
        
        self._finalize_speedup_analysis(**kwargs)
        
