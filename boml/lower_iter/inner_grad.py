# MIT License

# Copyright (c) 2020 Yaohua Liu

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
The base class in lower_iter to encapsulate the LL optimization strategies.BOMLOptimizer chooses
built-in or extended strategies in lower iter and returns iterative formats of the dynamical
system.
"""
from __future__ import print_function, absolute_import, division

from collections import OrderedDict

import tensorflow as tf

# import numpy as np
GRADIENT_NONE_MESSAGE = (
    "WARNING: the gradient w.r.t.the tf.Variable\n {}\n is None;\n "
    "Check the computational graph of the inner objective, and be sure you\n"
    "are not considering including variables that should not be there among the\n"
    "inner variables."
)


class BOMLInnerGradTrad(object):
    def __init__(self, update_op, dynamics, objective):
        """
        :param update_op: the tf operation to perform updates
        :param dynamics: the iterative formats of dynamical system
        :param objective: Lower-Level objective
        """
        self._updates_op = update_op
        self._dynamics = dynamics
        self._iteration = None
        self._initialization = None
        self._init_dyn = (
            None  # for phi_0 (will be a dictionary (state-variable, phi_0 op)
        )
        self.objective = objective
        self.bml_opt = None

    @staticmethod
    def compute_gradients(
        boml_opt,
        loss_inner,
        loss_outer=None,
        param_dict=OrderedDict(),
        var_list=None,
        **inner_kargs
    ):
        """
        :param boml_opt: instance of modified optimizers in the `optimizer` module
        :param loss_inner: Lower-Level objectives
        :param loss_outer: Upper-Level objectives
        :param param_dict: dictionary of general parameters for different algorithms
        :param var_list: the list of parameters in the base-learner
        :param inner_kargs: optional arguments for tensorflow optimizers, like global_step, gate_gradients
        :return: initialized instance of inner_grad for UL optimization
        """

        minimize_kargs = {
            inner_arg: inner_kargs[inner_arg]
            for inner_arg in set(inner_kargs.keys()) - set(param_dict.keys())
        }

        assert loss_inner is not None, "argument:inner_objective must be initialized"
        update_op, dynamics = boml_opt.minimize(
            loss_inner=loss_inner, var_list=var_list, *minimize_kargs
        )

        return BOMLInnerGradTrad(
            update_op=update_op, dynamics=dynamics, objective=loss_inner
        )  # loss_inner

    @property
    def apply_updates(self):
        """
        Descent step, as returned by `tf.train.Optimizer.apply_gradients`.
        :return:
        """
        return self._updates_op

    @property
    def iteration(self):
        """
        Performs a descent step (as return by `tf.train.Optimizer.apply_gradients`) and computes the values of
        the variables after it.

        :return: A list of operation that, after performing one iteration, return the value of the state variables
                    being optimized (possibly including auxiliary variables)
        """
        if self._iteration is None:
            with tf.control_dependencies([self._updates_op]):  # ?
                self._iteration = (
                    self._state_read()
                )  # performs an iteration and returns the
                # value of all variables in the state (ordered according to dyn)

        return self._iteration

    @property
    def initialization(self):
        """
        :return: a list of operations that return the values of the state variables for this
                    learning dynamics after the execution of the initialization operation. If
                    an initial dynamics is set, then it also executed.
        """
        if self._initialization is None:
            with tf.control_dependencies([tf.variables_initializer(self.state)]):
                if (
                    self._init_dyn is not None
                ):  # create assign operation for initialization
                    self._initialization = [
                        k.assign(v) for k, v in self._init_dyn.items()
                    ]
                    # return these new initialized values (and ignore variable initializers)
                else:
                    self._initialization = (
                        self._state_read()
                    )  # initialize state variables and
                    # return the initialized value

        return self._initialization

    @property
    def dynamics(self):
        """
        :return: A generator for the dynamics (state_variable_{k+1})
        """
        return self._dynamics.values()

    @property
    def state(self):
        """
        :return: A generator for all the state variables (optimized variables and possibly auxiliary variables)
        being optimized
        """
        return self._dynamics.keys()  # overridden in Adam

    def _state_read(self):
        """
        :return: generator of read value op for the state variables
        """
        return [
            v.read_value() for v in self.state
        ]  # not sure about read_value vs value

    def state_feed_dict(self, his):
        """
        Builds a feed dictionary of (past) states
        """
        return {v: his[k] for k, v in enumerate(self.state)}

    @property
    def init_dynamics(self):
        """
        :return: The initialization dynamics if it has been set, or `None` otherwise.
        """
        return None if self._init_dyn is None else list(self._init_dyn.items())

    def __lt__(self, other):  # make OptimizerDict sortable
        # TODO be sure that this is consistent
        assert isinstance(other, BOMLInnerGradTrad)
        return hash(self) < hash(other)

    def __len__(self):
        return len(self._dynamics)
