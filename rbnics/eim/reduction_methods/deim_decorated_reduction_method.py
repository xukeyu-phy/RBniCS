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

from rbnics.utils.decorators import exact_problem, Extends, override, ReductionMethodDecoratorFor, regenerate_reduced_problem_from_exact_reduced_problem
from rbnics.eim.problems import DEIM
from rbnics.eim.problems.eim_approximation import EIMApproximation as DEIMApproximation
from rbnics.eim.problems.time_dependent_eim_approximation import TimeDependentEIMApproximation as TimeDependentDEIMApproximation
from rbnics.eim.reduction_methods.eim_approximation_reduction_method import EIMApproximationReductionMethod as DEIMApproximationReductionMethod
from rbnics.eim.reduction_methods.time_dependent_eim_approximation_reduction_method import TimeDependentEIMApproximationReductionMethod as TimeDependentDEIMApproximationReductionMethod

@ReductionMethodDecoratorFor(DEIM)
def DEIMDecoratedReductionMethod(DifferentialProblemReductionMethod_DerivedClass):
    
    @Extends(DifferentialProblemReductionMethod_DerivedClass, preserve_class_name=True)
    class DEIMDecoratedReductionMethod_Class(DifferentialProblemReductionMethod_DerivedClass):
        @override
        def __init__(self, truth_problem, **kwargs):
            # Call the parent initialization
            DifferentialProblemReductionMethod_DerivedClass.__init__(self, truth_problem, **kwargs)
            # Storage for DEIM reduction methods
            self.DEIM_reductions = dict() # from term to dict of DEIMApproximationReductionMethod
            
            # Preprocess each term in the affine expansions
            for (term, DEIM_approximations_term) in self.truth_problem.DEIM_approximations.iteritems():
                self.DEIM_reductions[term] = dict()
                for (q, DEIM_approximations_term_q) in DEIM_approximations_term.iteritems():
                    assert isinstance(DEIM_approximations_term_q, (DEIMApproximation, TimeDependentDEIMApproximation))
                    if isinstance(DEIM_approximations_term_q, TimeDependentDEIMApproximation):
                        DEIMApproximationReductionMethodType = TimeDependentDEIMApproximationReductionMethod
                    else:
                        DEIMApproximationReductionMethodType = DEIMApproximationReductionMethod
                    self.DEIM_reductions[term][q] = DEIMApproximationReductionMethodType(DEIM_approximations_term_q)
                    
            # Retrieve value passed to decorator
            self._train_first = truth_problem._train_first
            del truth_problem._train_first
            
        ## OFFLINE: set maximum reduced space dimension (stopping criterion)
        @override
        def set_Nmax(self, Nmax, **kwargs):
            DifferentialProblemReductionMethod_DerivedClass.set_Nmax(self, Nmax, **kwargs)
            # Set Nmax of DEIM reductions
            def setter(DEIM_reduction, Nmax_DEIM):
                DEIM_reduction.set_Nmax(max(DEIM_reduction.Nmax, Nmax_DEIM)) # kwargs are not needed
            self._propagate_setter_from_kwargs_to_DEIM_reductions(setter, int, **kwargs)
            
        ## OFFLINE: set tolerance (stopping criterion)
        @override
        def set_tolerance(self, tol, **kwargs):
            DifferentialProblemReductionMethod_DerivedClass.set_tolerance(self, tol, **kwargs)
            # Set tolerance of DEIM reductions
            def setter(DEIM_reduction, tol_DEIM):
                DEIM_reduction.set_tolerance(max(DEIM_reduction.tol, tol_DEIM)) # kwargs are not needed
            self._propagate_setter_from_kwargs_to_DEIM_reductions(setter, float, **kwargs)
            
        ## OFFLINE: set the elements in the training set.
        @override
        def initialize_training_set(self, ntrain, enable_import=True, sampling=None, **kwargs):
            import_successful = DifferentialProblemReductionMethod_DerivedClass.initialize_training_set(self, ntrain, enable_import, sampling, **kwargs)
            # Since exact evaluation is required, we cannot use a distributed training set
            self.training_set.distributed_max = False
            # Initialize training set of DEIM reductions
            def setter(DEIM_reduction, ntrain_DEIM):
                return DEIM_reduction.initialize_training_set(ntrain_DEIM, enable_import, sampling) # kwargs are not needed
            import_successful_DEIM = self._propagate_setter_from_kwargs_to_DEIM_reductions(setter, int, **kwargs)
            return import_successful and import_successful_DEIM
            
        ## ERROR ANALYSIS: set the elements in the testing set.
        @override
        def initialize_testing_set(self, ntest, enable_import=False, sampling=None, **kwargs):
            import_successful = DifferentialProblemReductionMethod_DerivedClass.initialize_testing_set(self, ntest, enable_import, sampling, **kwargs)
            # Initialize testing set of DEIM reductions
            def setter(DEIM_reduction, ntest_DEIM):
                return DEIM_reduction.initialize_testing_set(ntest_DEIM, enable_import, sampling) # kwargs are not needed
            import_successful_DEIM = self._propagate_setter_from_kwargs_to_DEIM_reductions(setter, int, **kwargs)
            return import_successful and import_successful_DEIM
            
        def _propagate_setter_from_kwargs_to_DEIM_reductions(self, setter, Type, **kwargs):
            assert "DEIM" in kwargs
            kwarg_DEIM = kwargs["DEIM"]
            return_value = True # will be either a bool or None
            if isinstance(kwarg_DEIM, dict):
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    if len(self.DEIM_reductions[term]) > 0:
                        assert term in kwarg_DEIM, "Please provide a value for term " + str(term)
                        assert isinstance(kwarg_DEIM[term], (int, tuple))
                        if isinstance(kwarg_DEIM[term], int):
                            kwarg_DEIM[term] = [kwarg_DEIM[term]]*len(self.DEIM_reductions[term])
                        else:
                            assert max(self.DEIM_reductions[term].keys()) == len(kwarg_DEIM[term]) - 1
                        for (q, DEIM_reductions_term_q) in self.DEIM_reductions[term].iteritems():
                            assert isinstance(kwarg_DEIM[term][q], Type)
                            current_return_value = setter(DEIM_reductions_term_q, kwarg_DEIM[term][q])
                            return_value = current_return_value and return_value
            else:
                assert isinstance(kwarg_DEIM, Type)
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    for (_, DEIM_reduction_term_q) in DEIM_reductions_term.iteritems():
                        current_return_value = setter(DEIM_reduction_term_q, kwarg_DEIM)
                        return_value = current_return_value and return_value
            return return_value # an "and" with a None results in None, so this method returns only if necessary
            
        ## Perform the offline phase of the reduced order model
        @override
        def offline(self):
            assert self._train_first in ("DEIM", "Problem")
            if self._train_first == "DEIM":
                # Perform first the DEIM offline phase, ...
                bak_first_mu = tuple(list(self.truth_problem.mu))
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    for (_, DEIM_reduction_term_q) in DEIM_reductions_term.iteritems():
                        DEIM_reduction_term_q.offline()
                # ..., and then call the parent method.
                self.truth_problem.set_mu(bak_first_mu)
                return DifferentialProblemReductionMethod_DerivedClass.offline(self)
            else:
                bak_truth_problem = self.truth_problem
                self.truth_problem = exact_problem(bak_truth_problem)
                # Perform first parent offline phase (with exact operators)
                bak_first_mu = tuple(list(self.truth_problem.mu))
                exact_reduced_problem = DifferentialProblemReductionMethod_DerivedClass.offline(self)
                # Then carry out DEIM offline phase
                self.truth_problem.set_mu(bak_first_mu)
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    for (_, DEIM_reduction_term_q) in DEIM_reductions_term.iteritems():
                        DEIM_reduction_term_q.offline()
                # Restore the original truth problem
                self.truth_problem = bak_truth_problem
                # Re-generate a reduced problem associated to the original truth problem
                self.reduced_problem = regenerate_reduced_problem_from_exact_reduced_problem(self.truth_problem, self, exact_reduced_problem)
                return self.reduced_problem
    
        # Compute the error of the reduced order approximation with respect to the full order one
        # over the testing set
        @override
        def error_analysis(self, N=None, **kwargs):
            # Perform first the DEIM error analysis, ...
            if (
                "with_respect_to" not in kwargs # otherwise we assume the user was interested in computing the error w.r.t. 
                                                # an exact parametrized functions, 
                                                # so he probably is not interested in the error analysis of DEIM
                    and 
                (
                    "DEIM" not in kwargs        # otherwise we assume the user was interested in computing the error for a fixed number of DEIM basis
                                                # functions, thus he has already carried out the error analysis of DEIM
                        or
                    ("DEIM" in kwargs and kwargs["DEIM"] is not None) # shorthand to disable DEIM error analysis
                )
            ):
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    for (_, DEIM_reduction_term_q) in DEIM_reductions_term.iteritems():
                        DEIM_reduction_term_q.error_analysis(N)
            # ..., and then call the parent method.
            if "DEIM" in kwargs and kwargs["DEIM"] is None:
                del kwargs["DEIM"]
            DifferentialProblemReductionMethod_DerivedClass.error_analysis(self, N, **kwargs)
            
        # Compute the speedup of the reduced order approximation with respect to the full order one
        # over the testing set
        @override
        def speedup_analysis(self, N=None, **kwargs):
            # Perform first the DEIM speedup analysis, ...
            if (
                "with_respect_to" not in kwargs # otherwise we assume the user was interested in computing the speedup w.r.t. 
                                                # an exact parametrized functions, 
                                                # so he probably is not interested in the speedup analysis of DEIM
                    and
                (
                    "DEIM" not in kwargs        # otherwise we assume the user was interested in computing the speedup for a fixed number of DEIM basis
                                                # functions, thus he has already carried out the speedup analysis of DEIM
                        or
                    ("DEIM" in kwargs and kwargs["DEIM"] is not None) # shorthand to disable DEIM speedup analysis
                )
            ):
                for (term, DEIM_reductions_term) in self.DEIM_reductions.iteritems():
                    for (_, DEIM_reduction_term_q) in DEIM_reductions_term.iteritems():
                        DEIM_reduction_term_q.speedup_analysis(N)
            # ..., and then call the parent method.
            if "DEIM" in kwargs and kwargs["DEIM"] is None:
                del kwargs["DEIM"]
            DifferentialProblemReductionMethod_DerivedClass.speedup_analysis(self, N, **kwargs)
        
    # return value (a class) for the decorator
    return DEIMDecoratedReductionMethod_Class
    
