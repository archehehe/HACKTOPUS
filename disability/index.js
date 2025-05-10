// Toggle collapse
document.querySelector('.collapse-btn').addEventListener('click', () => {
    document.querySelector('.notnav-container').classList.toggle('collapsed');
  });
  
  // Sample data
  const navData = [
    {
      title: "Getting Started",
      icon: "📄",
      children: [
        { title: "Welcome", icon: "👋" },
        { title: "Tutorial", icon: "🎓" }
      ]
    },
    {
      title: "Projects",
      icon: "📂",
      children: [
        { title: "Web App", icon: "🌐" },
        { title: "Mobile", icon: "📱" }
      ]
    }
  ];
  
  // Render navigation
  function renderNav(items, container) {
    container.innerHTML = '';
    items.forEach(item => {
      const element = document.createElement('div');
      element.className = 'nav-item';
      element.innerHTML = `
        <span class="icon">${item.icon}</span>
        <span class="title">${item.title}</span>
        ${item.children ? '<span class="toggle">+</span>' : ''}
      `;
      
      if (item.children) {
        element.addEventListener('click', (e) => {
          if (!e.target.classList.contains('toggle')) {
            element.classList.toggle('expanded');
            const toggle = element.querySelector('.toggle');
            toggle.textContent = element.classList.contains('expanded') ? '-' : '+';
          }
        });
        
        const nestedContainer = document.createElement('div');
        nestedContainer.className = 'nested-items';
        renderNav(item.children, nestedContainer);
        element.appendChild(nestedContainer);
      }
      
      container.appendChild(element);
    });
  }
  
  // Initialize
  renderNav(navData, document.querySelector('.nav-items'));