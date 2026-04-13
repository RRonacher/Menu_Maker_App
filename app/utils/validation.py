"""
Recipe data validation module.

Ensures all macro fields (calories, protein, fat, carbs) are non-null 
and within plausible ranges to prevent dirty data from skewing the 
macro-balancing algorithm.
"""

from typing import Dict, List, Any, Optional, Tuple


class MacroRanges:
    """Define plausible nutritional ranges for a single serving."""
    
    """Calories: 50–2500 (typical single-serve meal range)"""
    CALORIES_MIN = 50
    CALORIES_MAX = 2500
    
    """Protein (g): 0–200 (beyond this is unrealistic for a single serving)"""
    PROTEIN_MIN = 0
    PROTEIN_MAX = 200
    
    """Fat (g): 0–150 (beyond this is unrealistic for a single serving)"""
    FAT_MIN = 0
    FAT_MAX = 150
    
    """Carbs (g): 0–400 (beyond this is unrealistic for a single serving)"""
    CARBS_MIN = 0
    CARBS_MAX = 400


class MacroValidator:
    """Validates recipe macro nutritional data against plausible ranges."""
    
    @staticmethod
    def validate_macros(
        calories: Any,
        protein: Any,
        fat: Any,
        carbs: Any
    ) -> Dict[str, Any]:
        """
        Validate macro nutrients.
        
        Args:
            calories: Calorie value (should be int or convertible to int)
            protein: Protein in grams (should be float or convertible)
            fat: Fat in grams (should be float or convertible)
            carbs: Carbs in grams (should be float or convertible)
        
        Returns:
            Dict with keys:
            - 'valid': bool, True if all validations pass
            - 'calories': Tuple[bool, Optional[str]] (valid, error_msg)
            - 'protein': Tuple[bool, Optional[str]]
            - 'fat': Tuple[bool, Optional[str]]
            - 'carbs': Tuple[bool, Optional[str]]
        """
        result = {
            'valid': True,
            'calories': MacroValidator._validate_calories(calories),
            'protein': MacroValidator._validate_protein(protein),
            'fat': MacroValidator._validate_fat(fat),
            'carbs': MacroValidator._validate_carbs(carbs),
        }
        
        # Mark as invalid if any field failed
        result['valid'] = all(
            field[0] for field_name, field in result.items() 
            if field_name != 'valid'
        )
        
        return result
    
    @staticmethod
    def _validate_calories(value: Any) -> Tuple[bool, Optional[str]]:
        """Validate calories field."""
        if value is None:
            return False, "Calories cannot be empty."
        
        try:
            cal = int(float(value))
            if cal < MacroRanges.CALORIES_MIN:
                msg = f"Calories must be at least {MacroRanges.CALORIES_MIN}."
                return False, msg
            if cal > MacroRanges.CALORIES_MAX:
                msg = f"Calories must be at most {MacroRanges.CALORIES_MAX}."
                return False, msg
            return True, None
        except (ValueError, TypeError):
            return False, "Calories must be a valid number."
    
    @staticmethod
    def _validate_protein(value: Any) -> Tuple[bool, Optional[str]]:
        """Validate protein field."""
        if value is None:
            return False, "Protein cannot be empty."
        
        try:
            prot = float(value)
            if prot < MacroRanges.PROTEIN_MIN:
                msg = f"Protein cannot be negative."
                return False, msg
            if prot > MacroRanges.PROTEIN_MAX:
                msg = f"Protein must be at most {MacroRanges.PROTEIN_MAX}g."
                return False, msg
            return True, None
        except (ValueError, TypeError):
            return False, "Protein must be a valid number."
    
    @staticmethod
    def _validate_fat(value: Any) -> Tuple[bool, Optional[str]]:
        """Validate fat field."""
        if value is None:
            return False, "Fat cannot be empty."
        
        try:
            fat = float(value)
            if fat < MacroRanges.FAT_MIN:
                msg = f"Fat cannot be negative."
                return False, msg
            if fat > MacroRanges.FAT_MAX:
                msg = f"Fat must be at most {MacroRanges.FAT_MAX}g."
                return False, msg
            return True, None
        except (ValueError, TypeError):
            return False, "Fat must be a valid number."
    
    @staticmethod
    def _validate_carbs(value: Any) -> Tuple[bool, Optional[str]]:
        """Validate carbs field."""
        if value is None:
            return False, "Carbs cannot be empty."
        
        try:
            carb = float(value)
            if carb < MacroRanges.CARBS_MIN:
                msg = f"Carbs cannot be negative."
                return False, msg
            if carb > MacroRanges.CARBS_MAX:
                msg = f"Carbs must be at most {MacroRanges.CARBS_MAX}g."
                return False, msg
            return True, None
        except (ValueError, TypeError):
            return False, "Carbs must be a valid number."
    
    @staticmethod
    def get_validation_errors(validation_result: Dict[str, Any]) -> List[str]:
        """
        Extract human-readable error messages from validation result.
        
        Args:
            validation_result: Result dict from validate_macros()
        
        Returns:
            List of error message strings (empty list if no errors)
        """
        errors = []
        for field_name in ['calories', 'protein', 'fat', 'carbs']:
            if field_name in validation_result:
                is_valid, error_msg = validation_result[field_name]
                if not is_valid and error_msg:
                    errors.append(error_msg)
        return errors
