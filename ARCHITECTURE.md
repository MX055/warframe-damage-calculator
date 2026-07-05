## Architecture

# Class Inheritance

```text
Build
└── Upgrade

Weapon
├── Ranged
│   ├── Primary
│   └── Secondary
└── Melee

WeaponState
├── RangedState
│   ├── PrimaryState
│   └── SecondaryState
└── MeleeState

TypedDict
├── WeaponField
│   ├── RangedField
│   │   ├── PrimaryField
│   │   └── SecondaryField
│   └── MeleeField
└── DamageField

WeaponCalculator
├── RangedCalculator
│   ├── PrimaryCalculator
│   └── SecondaryCalculator
└── MeleeCalculator

WeaponFormatter
├── RangedFormatter
│   ├── PrimaryFormatter
│   └── SecondaryFormatter
└── MeleeFormatter
```

# Class Ownership

```text
Weapon
│
├─ owns ─► WeaponCalculator
│          │
│          ├─ owns ─► WeaponState (base)
│          ├─ owns ─► WeaponState (modded)
│          ├─ owns ─► WeaponState (effective)
│          └─ owns ─► Build
│                     │
│                     └─ owns ─► Upgrade
│                                │
│                                └─ owns ─► dist
│
└─ owns ─► WeaponFormatter
           │
           └─ references ─► WeaponCalculator

Melee
│
├─ owns ─► MeleeCalculator
│          │
│          ├─ owns ─► MeleeState (base)
│          ├─ owns ─► MeleeState (modded)
│          ├─ owns ─► MeleeState (effective)
│          └─ owns ─► Build
│                     │
│                     └─ owns ─► Upgrade
│                                │
│                                └─ owns ─► dist
│
└─ owns ─► MeleeFormatter
           │
           └─ references ─► MeleeCalculator

Ranged
│
├─ owns ─► RangedCalculator
│          │
│          ├─ owns ─► RangedState (base)
│          ├─ owns ─► RangedState (modded)
│          ├─ owns ─► RangedState (effective)
│          └─ owns ─► Build
│                     │
│                     └─ owns ─► Upgrade
│                                │
│                                └─ owns ─► dist
│
└─ owns ─► RangedFormatter
           │
           └─ references ─► RangedCalculator

Primary
│
├─ owns ─► PrimaryCalculator
│          │
│          ├─ owns ─► PrimaryState (base)
│          ├─ owns ─► PrimaryState (modded)
│          ├─ owns ─► PrimaryState (effective)
│          └─ owns ─► Build
│                     │
│                     └─ owns ─► Upgrade
│                                │
│                                └─ owns ─► dist
│
└─ owns ─► PrimaryFormatter
           │
           └─ references ─► PrimaryCalculator

Secondary
│
├─ owns ─► SecondaryCalculator
│          │
│          ├─ owns ─► SecondaryState (base)
│          ├─ owns ─► SecondaryState (modded)
│          ├─ owns ─► SecondaryState (effective)
│          └─ owns ─► Build
│                     │
│                     └─ owns ─► Upgrade
│                                │
│                                └─ owns ─► dist
│
└─ owns ─► SecondaryFormatter
           │
           └─ references ─► SecondaryCalculator
```

# Package Architecture

```text
warframe_damage_calculator/
│
├── __init__.py
│
├── models/
│   │
│   ├── dist.py
│   ├── upgrade.py
│   ├── build.py
│   │
│   ├── weapon.py
│   ├── ranged.py
│   ├── primary.py
│   ├── secondary.py
│   └── melee.py
│
├── states/
│   │
│   ├── weapon_state.py
│   ├── ranged_state.py
│   ├── primary_state.py
│   ├── secondary_state.py
│   └── melee_state.py
│
├── fields/
│   │
│   ├── weapon_field.py
│   ├── ranged_field.py
│   ├── damage_field.py
│   ├── primary_field.py
│   ├── secondary_field.py
│   └── melee_field.py
│
├── calculators/
│   │
│   ├── weapon_calculator.py
│   ├── ranged_calculator.py
│   ├── primary_calculator.py
│   ├── secondary_calculator.py
│   └── melee_calculator.py
│
├── formatters/
│   │
│   ├── weapon_formatter.py
│   ├── ranged_formatter.py
│   ├── primary_formatter.py
│   ├── secondary_formatter.py
│   └── melee_formatter.py
│
└── utils/
    │
    ├── damage.py
    └── functions.py
```