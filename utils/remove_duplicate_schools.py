def remove_duplicate_schools(schools_list: List[SchoolAndDomain]) -> List[SchoolAndDomain]:
    """Remove duplicate schools from the list"""
    seen = set()
    unique_schools = []
    
    for school_domain in schools_list:
        # Normalize school name for comparison
        normalized_name = school_domain.school.lower().strip()
        
        if normalized_name not in seen:
            seen.add(normalized_name)
            unique_schools.append(school_domain)
        else:
            print(f"Skipped duplicate: {school_domain.school}")
    
    return unique_schools