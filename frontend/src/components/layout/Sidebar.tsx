import { NavLink } from "react-router-dom";

const navigation = [
  ["Dashboard", "/dashboard"],
  ["Tasks", "/tasks"],
  ["Recurring Tasks", "/tasks/recurring"],
  ["Projects", "/projects"],
  ["Daily Workflow", "/daily-workflow"],
  ["Categories", "/settings/categories"],
  ["Settings", "/settings"],
  ["Reports", "/reports"]
] as const;

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <NavLink className="brand" to="/dashboard">
        LifeManager
      </NavLink>
      <nav className="sidebar__nav">
        {navigation.map(([label, path]) => (
          <NavLink
            className={({ isActive }) =>
              isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
            }
            key={path}
            to={path}
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
