# -*- coding: utf-8 -*-

class WrongDataValueType(Exception):
    status_code = 400

    def __init__(self, expected_data_value_type, actual_data_value_type):
        Exception.__init__(self)
        self.expected_data_value_type = expected_data_value_type
        self.actual_data_value_type = actual_data_value_type
