#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All rights reserved.
"""
The Trainer for Cross-Entropy Method. The idea is that an ensemble of
 world models are fitted to predict transitions and reward functions.
A cross entropy method-based planner will then plan the best next action
based on simulation data generated by the fitted world models.

The idea is inspired by: https://arxiv.org/abs/1805.12114
"""
import logging
from typing import List, Union

import numpy as np
import reagent.types as rlt
import torch
from reagent.models.cem_planner import CEMPlannerNetwork
from reagent.parameters import CEMTrainerParameters
from reagent.training.rl_trainer_pytorch import RLTrainer
from reagent.training.training_data_page import TrainingDataPage
from reagent.training.world_model.mdnrnn_trainer import MDNRNNTrainer


logger = logging.getLogger(__name__)


class CEMTrainer(RLTrainer):
    def __init__(
        self,
        cem_planner_network: CEMPlannerNetwork,
        world_model_trainers: List[MDNRNNTrainer],
        parameters: CEMTrainerParameters,
        use_gpu: bool = False,
    ) -> None:
        super().__init__(parameters.rl, use_gpu=use_gpu)
        self.cem_planner_network = cem_planner_network
        self.world_model_trainers = world_model_trainers
        self.minibatch_size = parameters.mdnrnn.minibatch_size

    def train(self, training_batch):
        if isinstance(training_batch, TrainingDataPage):
            training_batch = training_batch.as_cem_training_batch()
        assert type(training_batch) is rlt.PreprocessedMemoryNetworkInput
        for i, trainer in enumerate(self.world_model_trainers):
            losses = trainer.train(training_batch)
            logger.info(
                "{}-th minibatch {}-th model: \n"
                "loss={}, bce={}, gmm={}, mse={} \n"
                "cum loss={}, cum bce={}, cum gmm={}, cum mse={}\n".format(
                    self.minibatch,
                    i,
                    losses["loss"],
                    losses["bce"],
                    losses["gmm"],
                    losses["mse"],
                    np.mean(trainer.cum_loss),
                    np.mean(trainer.cum_bce),
                    np.mean(trainer.cum_gmm),
                    np.mean(trainer.cum_mse),
                )
            )
        self.minibatch += 1
        logger.info("")

    @torch.no_grad()
    # pyre-fixme[14]: `internal_prediction` overrides method defined in `RLTrainer`
    #  inconsistently.
    def internal_prediction(
        self, state: torch.Tensor
    ) -> Union[rlt.SacPolicyActionSet, rlt.DqnPolicyActionSet]:
        """
        Only used by Gym. Return the predicted next action
        """
        output = self.cem_planner_network(rlt.FeatureData(state))
        if not self.cem_planner_network.discrete_action:
            return rlt.SacPolicyActionSet(greedy=output, greedy_propensity=1.0)
        return rlt.DqnPolicyActionSet(greedy=output[0])

    @torch.no_grad()
    def internal_reward_estimation(self, input):
        """
        Only used by Gym
        """
        raise NotImplementedError()
