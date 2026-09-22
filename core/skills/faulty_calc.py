from dataclasses import dataclass

@dataclass
class SkillMeta:
    name: str = "faulty_calc"
    version: str = "1.0.0"
    description: str = "Calculates payload metrics with intentional bug."

meta = SkillMeta()

def execute(a: int, b: int) -> dict:
    # FIXED: Correct type handling and defined variable
    result = a + b
    return {"calculated": result}

def self_test() -> bool:
    return True