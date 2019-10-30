import React from 'react';
import logo from './logo.svg';
import deducelogo from './deducelogo.png';
import './App.css';


class FileType extends React.Component {

  constructor(props) {
    super(props);
    this.handleSelectFileFormat = this.handleSelectFileFormat.bind(this);
  }

  handleSelectFileFormat(e) {
    this.props.onSelectFileFormat(e.target.value);
  }

  render() {
    return (
      <div class="card column">
        <div class="input-group">
          <label>File Format for Comparison</label>
          <select id="file_format" onChange={this.handleSelectFileFormat}>
            <option value="" selected="selected"></option>
            <option value="fits">fits</option>
            <option value="csv" >csv</option>
          </select>
        </div>
      </div>
    );
  }
}

class DataModelInfo extends React.Component {
  constructor(props) {
    super(props);
    this.handleHduSelect = this.handleHduSelect.bind(this);
    this.handleSelectFile = this.handleSelectFile.bind(this);

    this.state = {
      exampleFile: ""
    };
  }

  handleHduSelect(e) {
    this.props.onHduSelectChange(e.target.id);
  }

  handleSelectFile(e) {
    this.setState({ 
      exampleFile : e.target.value
    });
  }

  render() {
    if (this.props.fileFormat == "fits") {
      return (
        <div class="card column">
          <div class="card-title">Data Model Information</div>
          <div class="card-subsection">
            <div class="input-group">
              <label>Select Example File</label>
              <select id="file" onChange={this.handleSelectFile}>
                <option value="" selected="selected"></option>
                <option value="spCFrame-b1-00161868.fits" >spCFrame-b1-00161868.fits</option>
              </select>
            </div>
          </div>

         { this.state.exampleFile != "" &&
            <div>
              <div class="table-prompt">Which HDU's do you want to compare?</div>
              <table>
                <thead> 
                  <tr>
                    <th>&nbsp;</th>
                    <th>No</th>
                    <th>Name</th>
                    <th>HDU Type</th>
                    <th>Dimension</th>
                    <th>Content Type</th>
                  </tr>
                </thead>
                <tbody>
                {this.props.hdus.map((hdu) => (
                  <tr>
                    <td><input type="checkbox"  id={hdu[0]} name={hdu[0]} onChange={this.handleHduSelect} /></td>
                    <td>{hdu[0]}</td>
                    <td>{hdu[1]}</td>
                    <td>{hdu[3]}</td>
                    <td>({hdu[5][0]},{hdu[5][1]})</td>
                    <td><input type="text" /></td>
                  </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
        </div>
      );
    } else {
      return (null);
    }
  }
}

class VisInfo extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {
    if (this.props.selectedHDUS.length !== 0) {
      return (
        <div class="card column">
          <div class="card-title">Visualization Information</div>
          <div>
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Comparison Type</th>
                  <th>Visualization Type</th>
               </tr>
              </thead>
              <tbody>
              {this.props.selectedHDUS.map((index) => (
                <tr>
                  <td>{this.props.hdus[index][1]}</td>
                  <td><input type="text" /></td>
                  <td><input type="text" /></td>
                </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    } else {
      return (null);
    }
  }
}

class ComparingFiles extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {

    if (this.props.selectedHDUS.length !== 0) {
      return (
        <div class="card column">
          <div class="card-title">Comparing Files</div>
          <div class="radio-group">
            <input type="radio" />
            <label>Comparing 2 Files</label>
            <input type="radio" />
            <label>Comparing Multiple Files/Directories</label>
          </div>
          <div class="input-group">
            <label>Compare Files</label>
            <input type="text" />
          </div>
        </div>
      );
    } else {
      return (null);
    }
  }
}

class MainContent extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {
    return (
      <div class="maincontent flex-body">
          <SideBar />
          <MetaBuilder hdus={this.props.hdus}/> 
      </div>
    );
  }
}

class SideBar extends React.Component {
  render() {
    return (
      <div class="sidebar flex-sidebar"> 
        <div class="column">
          <div class="return">
            <i className='material-icons' style={{fontSize: '18px', width: '30px', verticalAlign: 'middle'}}>arrow_back_ios</i>Return to Overview
          </div>
          <div class="comparators">
            <div class="comparator-section-title">Custom Comparators</div>
          </div>
        </div>
      </div>
    );
  }
}

class MetaBuilder extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      selectedHDUS: [],
      fileFormat: ""
    };
    this.onHduSelectChange = this.onHduSelectChange.bind(this);
    this.onSelectFileFormat = this.onSelectFileFormat.bind(this);
  }

  onHduSelectChange(index) {
    if (this.state.selectedHDUS.includes(index)) {
      console.log("index is included" + index)
      this.setState({
        selectedHDUS: this.state.selectedHDUS.filter((i) => i !== index)
      });   
    } else {
      const list = this.state.selectedHDUS.concat(index);
      this.setState({
        selectedHDUS: list
      }); 
    }
    
  }

  onSelectFileFormat(format) {
    this.setState({ 
      fileFormat : format
    });
  }



  render() {
    return (
      <div class="metabuilder">
        <FileType onSelectFileFormat={this.onSelectFileFormat}/>
        <DataModelInfo 
          hdus={this.props.hdus} 
          selectedHDUS={this.state.selectedHDUS} 
          onHduSelectChange={this.onHduSelectChange} 
          fileFormat={this.state.fileFormat}
        />
        <VisInfo 
          hdus={this.props.hdus} 
          selectedHDUS={this.state.selectedHDUS}
        />
        <ComparingFiles selectedHDUS={this.state.selectedHDUS} />
      </div>
    );
  }
}


class HeaderBar extends React.Component {
  render() {
    return (
      <div class="header">
        <div class="flex-container logo">
          <div><img src={deducelogo} alt=""/></div>
          <div class="logo-text">Deduce</div>
        </div>
        <div class="flex-right rightnav">About</div>
        <div class="rightnav">Documentation</div>
      </div>
    );
  }
}



class App extends React.Component {

  state = {
    hdus: []
  }

  componentDidMount() {
    fetch('/api/fitsinfo')
    .then(res => res.json())
    .then((data) => {
      this.setState({ hdus: data })
    })
    .catch(
      console.log("failed")
    )
  }

  render() {
    return (
      <div className="App">
        <HeaderBar />
        <MainContent hdus={this.state.hdus}/>

      </div>
    );
  }
}

export default App;