import re

file_path = 'frontend/src/app/dashboard/settings/page.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update WorkExperience interface
content = content.replace(
'''interface WorkExperience {
  company: string;
  role: string;
  start: string;
  end: string;
  description: string;
}''',
'''interface WorkExperience {
  company: string;
  job_title: string;
  start_date: string;
  end_date: string;
  summary: string;
}''')

# 2. Update ProfileData
content = content.replace('work_experience: WorkExperience[];', 'work_experiences: WorkExperience[];')

# 3. Update all profile.work_experience to profile.work_experiences
content = content.replace('profile.work_experience', 'profile.work_experiences')

# 4. updateWorkExperience function keys
content = content.replace("'role'", "'job_title'")
content = content.replace("'start'", "'start_date'")
content = content.replace("'end'", "'end_date'")
content = content.replace("'description'", "'summary'")

# 5. exp object properties
content = content.replace('exp.role', 'exp.job_title')
content = content.replace('exp.start', 'exp.start_date')
content = content.replace('exp.end', 'exp.end_date')
content = content.replace('exp.description', 'exp.summary')

# 6. newExp object properties
content = content.replace(
'''    const newExp: WorkExperience = {
      company: '',
      role: '',
      start: '',
      end: '',
      description: ''
    };''',
'''    const newExp: WorkExperience = {
      company: '',
      job_title: '',
      start_date: '',
      end_date: '',
      summary: ''
    };''')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated frontend.')
