# Design Resources & Component Libraries

## shadcn/ui Resources

### Official Documentation & Components
- **Main Site**: https://ui.shadcn.com/
- **Component Gallery**: https://ui.shadcn.com/docs/components
- **Example Applications**: https://ui.shadcn.com/examples/dashboard
- **Theme Customizer**: https://ui.shadcn.com/themes

### Community Collections
- **Awesome shadcn/ui**: https://github.com/birobirobiro/awesome-shadcn-ui
  - 50+ high-quality open source templates
  - NextJS + shadcn/ui + Tailwind CSS + Framer Motion
- **shadcn UI Kit**: https://shadcnuikit.com/
  - Admin dashboards, templates, components
  - 9 pre-made dashboards, 4 web apps, 30+ subpages

### Design Tools
- **Figma Kit**: https://www.shadcndesign.com/
  - Comprehensive collection of customizable components
- **Figma Design System**: https://www.figma.com/community/file/1203061493325953101/shadcn-ui-design-system

### Interactive Tools
- **Official Theme Generator**: ui.shadcn.com/themes
- **Component Playground**: Available on component pages
- **Storybook Integration**: Many shadcn projects include Storybook demos

## Component Categories for Admin UI

### Layout & Navigation
- Card variants (simple, with header, interactive)
- Badge styles (outline, solid, destructive)
- Button variations (ghost, outline, default)
- Table components (sortable, filterable)

### Data Display
- Entity cards (current implementation)
- Metric cards with charts
- Status indicators
- Progress components

### Forms & Inputs
- Search components
- Filter selectors
- Form layouts
- Input variations

### Interactive Elements
- Modal dialogs
- Dropdown menus
- Tooltips
- Sheet components (side panels)

## Current Implementation Notes

### EntityCard Design Choices
- Switched from colorful domain-specific styling to neutral theme
- Reduced padding from `p-4` to `p-3` for modern minimalist look
- Uses `bg-muted` for icons instead of colored backgrounds
- Consistent `text-muted-foreground` coloring
- Subtle hover effects with `hover:border-primary/50`

### Theme Integration
- Using Home Assistant official color palette (#03a9f4 blue)
- Full dark mode support via CSS variables
- Inter font family for modern typography
- Proper accessibility with semantic colors

## Next Steps for UI Enhancement

1. **Browse Component Gallery**: Check https://ui.shadcn.com/docs/components for new patterns
2. **Explore Examples**: Review dashboard examples for layout inspiration
3. **Test Themes**: Use theme customizer for color scheme refinement
4. **Community Templates**: Check awesome-shadcn-ui for advanced patterns