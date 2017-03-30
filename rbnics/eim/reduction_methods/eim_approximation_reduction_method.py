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
import types
from rbnics.reduction_methods.base import ReductionMethod
from rbnics.backends import evaluate
from rbnics.backends.online import OnlineMatrix
from rbnics.utils.io import ErrorAnalysisTable, Folders, GreedySelectedParametersList, GreedyErrorEstimatorsList, SpeedupAnalysisTable, Timer
from rbnics.utils.mpi import print
from rbnics.utils.decorators import Extends, override

# Empirical interpolation method for the interpolation of parametrized functions
@Extends(ReductionMethod)
class EIMApproximationReductionMethod(ReductionMethod):
    
    ## Default initialization of members
    @override
    def __init__(self, EIM_approximation):
        # Call the parent initialization
        ReductionMethod.__init__(self, EIM_approximation.folder_prefix, EIM_approximation.mu_range)
        
        # $$ OFFLINE DATA STRUCTURES $$ #
        # High fidelity problem
        self.EIM_approximation = EIM_approximation
        # Declare a new container to store the snapshots
        self.snapshots_container = self.EIM_approximation.parametrized_expression.create_snapshots_container()
        # I/O
        self.folder["snapshots"] = self.folder_prefix + "/" + "snapshots"
        self.folder["post_processing"] = self.folder_prefix + "/" + "post_processing"
        self.greedy_selected_parameters = GreedySelectedParametersList()
        self.greedy_errors = GreedyErrorEstimatorsList()
        #
        self._offline__mu_index = 0
        # By default set a tolerance slightly larger than zero, in order to 
        # stop greedy iterations in trivial cases by default
        self.tol = 1e-15
    
    @override
    def initialize_training_set(self, ntrain, enable_import=True, sampling=None, **kwargs):
        import_successful = ReductionMethod.initialize_training_set(self, ntrain, enable_import, sampling)
        # Since exact evaluation is required, we cannot use a distributed training set
        self.training_set.distributed_max = False
        return import_successful
    
    ## Initialize data structures required for the offline phase
    @override
    def _init_offline(self):
        # Prepare folders and init EIM approximation
        all_folders = Folders()
        all_folders.update(self.folder)
        all_folders.update(self.EIM_approximation.folder)
        all_folders.pop("testing_set") # this is required only in the error analysis
        at_least_one_folder_created = all_folders.create()
        if not at_least_one_folder_created:
            self.EIM_approximation.init("online")
            return False # offline construction should be skipped, since data are already available
        else:
            self.EIM_approximation.init("offline")
            return True # offline construction should be carried out
            
    ## Finalize data structures required after the offline phase
    @override
    def _finalize_offline(self):
        self.EIM_approximation.init("online")
    
    ## Perform the offline phase of EIM
    @override
    def offline(self):
        need_to_do_offline_stage = self._init_offline()
        if not need_to_do_offline_stage:
            return self.EIM_approximation
            
        interpolation_method_name = self.EIM_approximation.parametrized_expression.interpolation_method_name()
        description = self.EIM_approximation.parametrized_expression.description()
        
        # Evaluate the parametrized expression for all parameters in the training set
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " preprocessing phase begins for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        for (run, mu) in enumerate(self.training_set):
            print(":::::::::::::::::::::::::::::: " + interpolation_method_name + " run =", run, "::::::::::::::::::::::::::::::")
            
            self.EIM_approximation.set_mu(mu)
            
            print("evaluate parametrized expression at mu =", mu)
            self.EIM_approximation.evaluate_parametrized_expression()
            self.EIM_approximation.export_solution(self.folder["snapshots"], "truth_" + str(run))
            
            print("add to snapshots")
            self.add_to_snapshots(self.EIM_approximation.snapshot)

            print("")
            
        # If basis generation is POD, compute the first POD modes of the snapshots
        if self.EIM_approximation.basis_generation == "POD":
            print("compute basis")
            N_POD = self.compute_basis_POD()
            print("")
        
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " preprocessing phase ends for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " offline phase begins for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        # Arbitrarily start from the first parameter in the training set (Greedy only)
        if self.EIM_approximation.basis_generation == "Greedy":
            self.EIM_approximation.set_mu(self.training_set[0])
            self._offline__mu_index = 0
            
        # Carry out greedy selection
        if self.EIM_approximation.basis_generation == "Greedy":
            relative_error_max = 2.*self.tol
            while self.EIM_approximation.N < self.Nmax and relative_error_max >= self.tol:
                print(":::::::::::::::::::::::::::::: " + interpolation_method_name + " N =", self.EIM_approximation.N, "::::::::::::::::::::::::::::::")
            
                mu_index = self._offline__mu_index
                print("solve interpolation for mu =", self.training_set[mu_index])
                self.EIM_approximation.solve()
                
                print("compute and locate maximum interpolation error")
                self.EIM_approximation.snapshot = self.load_snapshot()
                (error, maximum_error, maximum_location) = self.EIM_approximation.compute_maximum_interpolation_error()
                
                print("update locations with", maximum_location)
                self.update_interpolation_locations(maximum_location)
                
                print("update basis")
                self.update_basis_greedy(error, maximum_error)
                
                print("update interpolation matrix")
                self.update_interpolation_matrix()
                
                print("find next mu")
                (error_max, relative_error_max) = self.greedy()
                print("maximum interpolation error =", error_max)
                print("maximum interpolation relative error =", relative_error_max)
                
                print("")
                
        else:
            while self.EIM_approximation.N < N_POD:
                print(":::::::::::::::::::::::::::::: " + interpolation_method_name + " N =", self.EIM_approximation.N, "::::::::::::::::::::::::::::::")
            
                print("solve interpolation for basis number", self.EIM_approximation.N)
                self.EIM_approximation._solve(self.EIM_approximation.Z[self.EIM_approximation.N])
                
                print("compute and locate maximum interpolation error")
                self.EIM_approximation.snapshot = self.EIM_approximation.Z[self.EIM_approximation.N]
                (error, maximum_error, maximum_location) = self.EIM_approximation.compute_maximum_interpolation_error()
                
                print("update locations with", maximum_location)
                self.update_interpolation_locations(maximum_location)
                
                self.EIM_approximation.N += 1
                
                print("update interpolation matrix")
                self.update_interpolation_matrix()
                
                print("")
            
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " offline phase ends for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        # mu_index does not make any sense from now on (Greedy only)
        if self.EIM_approximation.basis_generation == "Greedy":
            self._offline__mu_index = None
        
        self._finalize_offline()
        return self.EIM_approximation
        
    ## Update the snapshots container
    def add_to_snapshots(self, snapshot):
        self.snapshots_container.enrich(snapshot)
        
    ## Update basis (greedy version)
    def update_basis_greedy(self, error, maximum_error):
        self.EIM_approximation.Z.enrich(error/maximum_error)
        self.EIM_approximation.Z.save(self.EIM_approximation.folder["basis"], "basis")
        self.EIM_approximation.N += 1

    ## Update basis (POD version)
    def compute_basis_POD(self):
        POD = self.EIM_approximation.parametrized_expression.create_POD_container()
        POD.store_snapshot(self.snapshots_container)
        (_, Z, N) = POD.apply(self.Nmax, self.tol)
        self.EIM_approximation.Z.enrich(Z)
        self.EIM_approximation.Z.save(self.EIM_approximation.folder["basis"], "basis")
        # do not increment self.EIM_approximation.N
        POD.print_eigenvalues(N)
        POD.save_eigenvalues_file(self.folder["post_processing"], "eigs")
        POD.save_retained_energy_file(self.folder["post_processing"], "retained_energy")
        return N
        
    def update_interpolation_locations(self, maximum_location):
        self.EIM_approximation.interpolation_locations.append(maximum_location)
        self.EIM_approximation.interpolation_locations.save(self.EIM_approximation.folder["reduced_operators"], "interpolation_locations")
    
    ## Assemble the interpolation matrix
    def update_interpolation_matrix(self):
        self.EIM_approximation.interpolation_matrix[0] = evaluate(self.EIM_approximation.Z[:self.EIM_approximation.N], self.EIM_approximation.interpolation_locations)
        self.EIM_approximation.interpolation_matrix.save(self.EIM_approximation.folder["reduced_operators"], "interpolation_matrix")
            
    ## Load the precomputed snapshot
    def load_snapshot(self):
        assert self.EIM_approximation.basis_generation == "Greedy"
        mu = self.EIM_approximation.mu
        mu_index = self._offline__mu_index
        assert mu_index is not None
        assert mu == self.training_set[mu_index]
        return self.snapshots_container[mu_index]
        
    ## Choose the next parameter in the offline stage in a greedy fashion
    def greedy(self):
        assert self.EIM_approximation.basis_generation == "Greedy"
        def solve_and_computer_error(mu, index):
            self._offline__mu_index = index
            self.EIM_approximation.set_mu(mu)
            
            self.EIM_approximation.solve()
            self.EIM_approximation.snapshot = self.load_snapshot()
            (_, err, _) = self.EIM_approximation.compute_maximum_interpolation_error()
            return err
            
        (error_max, error_argmax) = self.training_set.max(solve_and_computer_error, abs)
        self.EIM_approximation.set_mu(self.training_set[error_argmax])
        self._offline__mu_index = error_argmax
        self.greedy_selected_parameters.append(self.training_set[error_argmax])
        self.greedy_selected_parameters.save(self.folder["post_processing"], "mu_greedy")
        self.greedy_errors.append(error_max)
        self.greedy_errors.save(self.folder["post_processing"], "error_max")
        if abs(self.greedy_errors[0]) > 0.:
            return (abs(error_max), abs(error_max/self.greedy_errors[0]))
        else:
            # Trivial case, greedy will stop at the first iteration
            assert len(self.greedy_errors) == 1
            return (0., 0.)
    
    # Compute the error of the empirical interpolation approximation with respect to the
    # exact function over the testing set
    @override
    def error_analysis(self, N=None, **kwargs):
        if N is None:
            N = self.EIM_approximation.N
        assert len(kwargs) == 0 # not used in this method
            
        self._init_error_analysis(**kwargs)
        
        interpolation_method_name = self.EIM_approximation.parametrized_expression.interpolation_method_name()
        description = self.EIM_approximation.parametrized_expression.description()
        
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " error analysis begins for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        error_analysis_table = ErrorAnalysisTable(self.testing_set)
        error_analysis_table.set_Nmax(N)
        error_analysis_table.add_column("error", group_name="eim", operations=("mean", "max"))
        
        for (run, mu) in enumerate(self.testing_set):
            print(":::::::::::::::::::::::::::::: " + interpolation_method_name + " run =", run, "::::::::::::::::::::::::::::::")
            
            self.EIM_approximation.set_mu(mu)
            
            # Evaluate the exact function on the truth grid
            self.EIM_approximation.evaluate_parametrized_expression()
            
            for n in range(1, N + 1): # n = 1, ... N
                self.EIM_approximation.solve(n)
                (_, error_analysis_table["error", n, run], _) = self.EIM_approximation.compute_maximum_interpolation_error(n)
                error_analysis_table["error", n, run] = abs(error_analysis_table["error", n, run])
        
        # Print
        print("")
        print(error_analysis_table)
        
        print("")
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " error analysis ends for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        self._finalize_error_analysis(**kwargs)
        
    # Compute the speedup of the empirical interpolation approximation with respect to the
    # exact function over the testing set
    @override
    def speedup_analysis(self, N=None, **kwargs):
        if N is None:
            N = self.EIM_approximation.N
        assert len(kwargs) == 0 # not used in this method
            
        self._init_speedup_analysis(**kwargs)
        
        interpolation_method_name = self.EIM_approximation.parametrized_expression.interpolation_method_name()
        description = self.EIM_approximation.parametrized_expression.description()
        
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " speedup analysis begins for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        speedup_analysis_table = SpeedupAnalysisTable(self.testing_set)
        speedup_analysis_table.set_Nmax(N)
        speedup_analysis_table.add_column("speedup", group_name="speedup", operations=("min", "mean", "max"))
        
        evaluate_timer = Timer("parallel")
        EIM_timer = Timer("serial")
        
        for (run, mu) in enumerate(self.testing_set):
            print(":::::::::::::::::::::::::::::: " + interpolation_method_name + " run =", run, "::::::::::::::::::::::::::::::")
            
            self.EIM_approximation.set_mu(mu)
            
            # Evaluate the exact function on the truth grid
            evaluate_timer.start()
            self.EIM_approximation.evaluate_parametrized_expression()
            elapsed_evaluate = evaluate_timer.stop()
            
            for n in range(1, N + 1): # n = 1, ... N
                EIM_timer.start()
                self.EIM_approximation.solve(n)
                elapsed_EIM = EIM_timer.stop()
                speedup_analysis_table["speedup", n, run] = elapsed_evaluate/elapsed_EIM
        
        # Print
        print("")
        print(speedup_analysis_table)
        
        print("")
        print("==============================================================")
        print("=" + "{:^60}".format(interpolation_method_name + " speedup analysis ends for") + "=")
        print("=" + "=\n=".join('{:^60}'.format(s) for s in description) + "=")
        print("==============================================================")
        print("")
        
        self._finalize_speedup_analysis(**kwargs)
        
    ## Initialize data structures required for the speedup analysis phase
    @override
    def _init_speedup_analysis(self, **kwargs): 
        # Make sure to clean up snapshot cache to ensure that parametrized
        # expression evaluation is actually carried out
        self.EIM_approximation.snapshot_cache.clear()
        # ... and also disable the capability of importing truth solutions
        self._speedup_analysis__original_import_solution = self.EIM_approximation.import_solution
        def disabled_import_solution(self_, folder, filename, solution=None):
            return False
        self.EIM_approximation.import_solution = types.MethodType(disabled_import_solution, self.EIM_approximation)
        
    ## Finalize data structures required after the speedup analysis phase
    @override
    def _finalize_speedup_analysis(self, **kwargs):
        # Restore the capability to import truth solutions
        self.EIM_approximation.import_solution = self._speedup_analysis__original_import_solution
        del self._speedup_analysis__original_import_solution
    
