import React, { useState, useEffect, useRef } from 'react';

const YIELD_VAULT_CODE = `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title YieldVault
 * @notice Simplified yield-bearing vault demonstrating reentrancy and access control.
 */
contract YieldVault {
    address public owner;
    mapping(address => uint256) public balances;
    bool private locked;

    event Deposit(address indexed sender, uint256 amount);
    event Withdraw(address indexed to, uint256 amount);

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "Zero deposit");
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    // Vulnerable withdraw function without reentrancy guard or CEI pattern
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // External call before state mutation
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] -= amount;
        emit Withdraw(msg.sender, amount);
    }

    function emergencyDrain() external {
        require(msg.sender == owner, "Only owner");
        payable(owner).transfer(address(this).balance);
    }
}
`;

const REENTRANCY_CLASSIC_CODE = `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract ReentrancyClassic {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 balance = balances[msg.sender];
        require(balance > 0, "No balance");

        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "Transfer failed");

        balances[msg.sender] = 0;
    }
}
`;

const ERC4626_CODE = `// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract ERC4626VulnerableVault {
    IERC20 public immutable asset;
    uint256 public totalAssets;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    constructor(IERC20 _asset) {
        asset = _asset;
        totalAssets = 100;
        totalSupply = 50;
    }

    function convertToShares(uint256 assets) public view returns (uint256) {
        if (totalAssets == 0 || totalSupply == 0) return assets;
        return (assets * totalSupply) / totalAssets;
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        if (totalSupply == 0) return shares;
        return (shares * totalAssets) / totalSupply;
    }

    function previewDeposit(uint256 assets) public view returns (uint256) {
        if (totalAssets == 0 || totalSupply == 0) return assets;
        return (assets * totalSupply + (totalAssets - 1)) / totalAssets;
    }

    function previewRedeem(uint256 shares) public view returns (uint256) {
        if (totalSupply == 0) return shares;
        return (shares * totalAssets + (totalSupply - 1)) / totalSupply;
    }

    function deposit(uint256 assets, address receiver) external returns (uint256 shares) {
        shares = previewDeposit(assets);
        totalAssets += assets;
        totalSupply += shares;
        balanceOf[receiver] += shares;
    }

    function withdraw(uint256 assets, address receiver, address owner) external returns (uint256 shares) {
        shares = convertToShares(assets);
        require(balanceOf[owner] >= shares, "INSUFFICIENT_SHARES");
        balanceOf[owner] -= shares;
        totalSupply -= shares;
        totalAssets -= assets;
    }
}
`;

const CAPPED_TOKEN_CODE = `// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract CappedToken {
    address public owner;
    uint256 public constant MAX_SUPPLY = 1000000;
    uint256 public totalSupply;
    mapping(address => uint256) public balances;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function mint(address to, uint256 amount) external onlyOwner {
        require(totalSupply + amount <= MAX_SUPPLY, "EXCEEDS_CAP");
        totalSupply += amount;
        balances[to] += amount;
    }
}
`;

const PRESET_CONTRACTS = [
  {
    name: 'YieldVault.sol',
    size: '1.2 KB',
    description: 'DeFi yield vault with reentrancy & access control',
    code: YIELD_VAULT_CODE,
  },
  {
    name: 'ReentrancyClassic.sol',
    size: '0.8 KB',
    description: 'The DAO classic ETH external call drain',
    code: REENTRANCY_CLASSIC_CODE,
  },
  {
    name: 'ERC4626Vulnerable.sol',
    size: '1.8 KB',
    description: 'Tokenized vault share inflation & rounding exploit',
    code: ERC4626_CODE,
  },
  {
    name: 'CappedToken.sol',
    size: '0.6 KB',
    description: 'Supply cap and centralized owner minting permissions',
    code: CAPPED_TOKEN_CODE,
  },
];

/**
 * FileDropZone component.
 * User-friendly file upload target with drag & drop, interactive Files Dropdown, and sample presets.
 */
export function FileDropZone({ onFileSelect }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [fileSizeStr, setFileSizeStr] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    }
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFileName(file.name);
      setFileSizeStr(`${(file.size / 1024).toFixed(1)} KB`);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (onFileSelect) onFileSelect(event.target.result, file.name);
      };
      reader.onerror = (err) => {
        console.error('Failed to read dropped file:', err);
      };
      reader.readAsText(file);
    }
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      const file = files[0];
      setSelectedFileName(file.name);
      setFileSizeStr(`${(file.size / 1024).toFixed(1)} KB`);
      setIsDropdownOpen(false);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (onFileSelect) onFileSelect(event.target.result, file.name);
      };
      reader.onerror = (err) => {
        console.error('Failed to read selected file:', err);
      };
      reader.readAsText(file);
    }
  };

  const handleSelectPreset = (name, code, size) => {
    setSelectedFileName(name);
    setFileSizeStr(size);
    setIsDropdownOpen(false);
    if (onFileSelect) {
      onFileSelect(code, name);
    }
  };

  const handleLoadSample = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    handleSelectPreset('YieldVault.sol', YIELD_VAULT_CODE, '1.2 KB');
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`border-2 border-dashed p-6 transition-all rounded-md bg-[#1D1916] flex flex-col items-center justify-center gap-3 text-center relative ${
        isDragOver
          ? 'border-primary bg-[#26211D] ring-2 ring-primary/20'
          : 'border-[#3A332D] hover:border-primary/80'
      }`}
    >
      <div className="font-label-caps text-xs text-primary font-bold tracking-wider uppercase">
        {isDragOver ? 'Drop Solidity File Here' : 'Contract File Ingestion'}
      </div>

      <div className="font-headline-sm text-sm font-semibold text-on-surface">
        Drag & drop your contract, or choose a file from the dropdown
      </div>

      <p className="font-body-sm text-xs text-on-surface-variant max-w-md">
        Supports Solidity source files (<code className="text-primary font-mono">.sol</code>), standard JSON input, or flattened contracts.
      </p>

      {/* Action Buttons: Solid, high-contrast, prominent styling with Files Dropdown */}
      <div className="flex flex-wrap items-center justify-center gap-3 mt-1 z-30">
        {/* Browse Files Button with interactive Files Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            id="browse-files-dropdown-button"
            onClick={() => setIsDropdownOpen((prev) => !prev)}
            style={{
              backgroundColor: '#FFBB49',
              color: '#14110F',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '10px 22px',
              borderRadius: '4px',
              fontWeight: '700',
              fontSize: '12px',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              cursor: 'pointer',
              border: 'none',
              boxShadow: '0 2px 8px rgba(255, 187, 73, 0.35)',
              userSelect: 'none',
            }}
            className="hover:bg-[#FFAE24] active:scale-[0.98] transition-all font-label-caps"
            aria-expanded={isDropdownOpen}
            aria-haspopup="true"
          >
            <svg
              className="w-4 h-4 shrink-0 pointer-events-none"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              style={{ strokeWidth: 2.5 }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span>Browse Files</span>
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 pointer-events-none ${isDropdownOpen ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              style={{ strokeWidth: 2.5 }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Files Dropdown Menu */}
          {isDropdownOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 60,
                width: '340px',
                maxWidth: '90vw',
              }}
              className="bg-[#1C1815] border border-[#FFBB49]/70 rounded-md shadow-2xl p-2 text-left flex flex-col gap-1 ring-1 ring-black/80 animate-in fade-in zoom-in-95 duration-100"
            >
              <div className="px-3 py-1.5 text-[10px] font-label-caps text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] flex items-center justify-between">
                <span>Contract Files Dropdown</span>
                <span className="text-[10px] text-outline font-normal">Pick or upload</span>
              </div>

              {/* Option 1: Native file input from device */}
              <label className="flex items-center gap-3 px-3 py-2.5 text-xs text-on-surface hover:bg-[#2A2420] hover:text-primary rounded cursor-pointer transition-colors font-medium border border-transparent hover:border-[#3A332D]">
                <input
                  type="file"
                  accept=".sol,.zip,.json,.txt,text/*,*"
                  className="sr-only"
                  onClick={(e) => {
                    e.stopPropagation();
                    e.target.value = '';
                  }}
                  onChange={handleFileInput}
                />
                <div className="w-6 h-6 rounded bg-primary/10 border border-primary/30 flex items-center justify-center shrink-0">
                  <svg className="w-3.5 h-3.5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <div className="flex flex-col">
                  <span className="font-semibold text-primary">Upload from Device...</span>
                  <span className="text-[10px] text-outline">Open local file (.sol, .zip, .json)</span>
                </div>
              </label>

              <div className="my-1 border-t border-[#3A332D] px-3 pt-1.5 pb-0.5 text-[9px] font-label-caps text-outline uppercase tracking-wider">
                Built-in Contract Suite
              </div>

              {/* Preset Contract Options */}
              {PRESET_CONTRACTS.map((contract) => (
                <button
                  key={contract.name}
                  type="button"
                  onClick={() => handleSelectPreset(contract.name, contract.code, contract.size)}
                  className={`flex items-center justify-between px-3 py-2 text-xs text-left rounded transition-colors border ${
                    selectedFileName === contract.name
                      ? 'bg-[#2A2420] border-primary text-primary font-semibold'
                      : 'border-transparent text-on-surface hover:bg-[#241F1B] hover:text-primary hover:border-[#3A332D]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-primary font-mono text-sm">📄</span>
                    <div className="flex flex-col">
                      <span className="font-mono text-xs font-medium">{contract.name}</span>
                      <span className="text-[10px] text-outline">{contract.description}</span>
                    </div>
                  </div>
                  <span className="font-mono text-[10px] text-outline bg-[#14110F] px-1.5 py-0.5 rounded border border-[#3A332D] shrink-0">
                    {contract.size}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 1-Click Load Sample Contract button */}
        <button
          type="button"
          onClick={handleLoadSample}
          style={{
            backgroundColor: '#2A2420',
            color: '#E9E1DD',
            border: '1px solid #3A332D',
            padding: '10px 18px',
            borderRadius: '4px',
            fontWeight: '600',
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            cursor: 'pointer',
          }}
          className="hover:text-primary hover:border-primary transition-all font-label-caps"
        >
          Load Sample Contract
        </button>
      </div>

      {/* Active File Feedback Pill */}
      {selectedFileName && (
        <div className="mt-2 px-3 py-1.5 bg-[#14110F] border border-[#3A332D] rounded flex items-center gap-3 text-xs font-code-sm">
          <span className="text-outline">Active File:</span>
          <span className="text-primary font-semibold font-mono">{selectedFileName}</span>
          <span className="text-on-surface-variant">({fileSizeStr})</span>
          <span className="text-[#8FA84A] font-semibold text-[11px]">• Ready to audit</span>
        </div>
      )}
    </div>
  );
}
